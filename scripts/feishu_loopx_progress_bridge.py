#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark.message_card import (
    build_lark_markdown_reply_card,
    compact_markdown,
    extract_reply_message_id,
)
from loopx.capabilities.lark.bridge_commands import (
    bridge_help_text,
    loopx_check_text,
    loopx_scheduler_next_batch_text,
    loopx_scheduler_plan_text,
    loopx_status_text,
)
from loopx.capabilities.lark.bridge_actions import todo_commands_for_action
from loopx.capabilities.lark.bridge_requests import build_feishu_request_todo_args
from loopx.capabilities.lark.progress_reporter import (
    ProgressNotification,
    build_acceptance_notification,
    build_bridge_error_notification,
    build_progress_notification,
    should_emit_notification,
)


HOME = Path.home()
CONTROL_ROOT = Path(os.environ.get("LOOPX_CONTROL_ROOT", os.getcwd())).expanduser()
LOOPX_BIN = os.environ.get("LOOPX_BIN", "loopx")
LOOPX_REGISTRY = os.environ.get("LOOPX_REGISTRY", ".loopx/registry.json")
LOOPX_GOAL_ID = os.environ.get("LOOPX_GOAL_ID", "default")
LOOPX_AGENT_ID = os.environ.get("LOOPX_AGENT_ID", "codex-devbox")
POLL_SECONDS = float(os.environ.get("LOOPX_FEISHU_PROGRESS_POLL_SECONDS", "45"))
STATE_FILE = Path(
    os.environ.get(
        "LOOPX_FEISHU_PROGRESS_STATE",
        str(HOME / ".config/loopx/feishu-progress-bridge-state.json"),
    )
).expanduser()
LOG_FILE = Path(
    os.environ.get(
        "LOOPX_FEISHU_PROGRESS_LOG",
        str(HOME / ".config/loopx/feishu-progress-bridge.log"),
    )
).expanduser()
BOT_MAX_TEXT_CHARS = int(os.environ.get("LOOPX_FEISHU_MAX_TEXT_CHARS", "1800"))
EVENT_TYPES = tuple(
    item.strip()
    for item in os.environ.get("LOOPX_FEISHU_EVENT_TYPES", "im.message.receive_v1,card.action.trigger").split(",")
    if item.strip()
)
SENSITIVE_PARAM_RE = re.compile(
    r"((?:access_key|authorization|secret|ticket|token|tenant_access_token|app_access_token|refresh_token)=)[^&\s]+",
    re.IGNORECASE,
)
TODO_ID_RE = re.compile(r"\btodo_[A-Za-z0-9_]+\b")
STATE_SCHEMA_VERSION = "loopx_feishu_progress_bridge_state_v2"
KEY_EVENT_STAGES = {"user_action", "blocked", "done", "bridge_error:status", "bridge_error:quota"}
DEFAULT_LAUNCH_AGENT_LABEL = "dev.loopx.feishu-progress-bridge"


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": STATE_SCHEMA_VERSION, "todos": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        todos = data.get("todos")
        if not isinstance(todos, dict):
            todos = {}
        data["schema_version"] = STATE_SCHEMA_VERSION
        data["todos"] = todos
        for todo_id, item in list(todos.items()):
            if not isinstance(item, dict):
                todos.pop(todo_id, None)
                continue
            item.setdefault("todo_id", todo_id)
            item.setdefault("progress_message_id", item.get("reply_message_id") or "")
            item.setdefault("last_key_fingerprint", "")
            item.setdefault("last_key_stage", "")
            if not isinstance(item.get("action_audit"), list):
                item["action_audit"] = []
        return data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)

    def track_todo(
        self,
        *,
        todo_id: str,
        message_id: str,
        request_text: str,
        goal_id: str,
        agent_id: str,
        request_lane: str = "",
        initial_fingerprint: str | None = None,
    ) -> None:
        now = utc_now()
        with self.lock:
            todos = self.data.setdefault("todos", {})
            previous = todos.get(todo_id) if isinstance(todos.get(todo_id), dict) else {}
            todos[todo_id] = {
                **previous,
                "todo_id": todo_id,
                "message_id": message_id,
                "request_text": request_text,
                "goal_id": goal_id,
                "agent_id": agent_id,
                "request_lane": request_lane or previous.get("request_lane") or "",
                "created_at": previous.get("created_at") or now,
                "updated_at": now,
                "closed": bool(previous.get("closed", False)),
                "progress_message_id": previous.get("progress_message_id") or "",
                "last_fingerprint": initial_fingerprint or previous.get("last_fingerprint"),
                "last_stage": previous.get("last_stage"),
                "last_key_fingerprint": previous.get("last_key_fingerprint") or "",
                "last_key_stage": previous.get("last_key_stage") or "",
                "action_audit": previous.get("action_audit") if isinstance(previous.get("action_audit"), list) else [],
            }
            self.save()

    def todo(self, todo_id: str) -> dict[str, Any]:
        with self.lock:
            item = self.data.get("todos", {}).get(todo_id)
            return dict(item) if isinstance(item, dict) else {}

    def active_todos(self) -> list[dict[str, Any]]:
        with self.lock:
            todos = self.data.get("todos") if isinstance(self.data.get("todos"), dict) else {}
            return [
                dict(item)
                for item in todos.values()
                if isinstance(item, dict) and not item.get("closed") and item.get("message_id")
            ]

    def update_after_notification(
        self,
        todo_id: str,
        notification: ProgressNotification,
        *,
        progress_message_id: str | None = None,
        key_event_sent: bool = False,
    ) -> None:
        with self.lock:
            todos = self.data.setdefault("todos", {})
            item = todos.get(todo_id)
            if not isinstance(item, dict):
                return
            if progress_message_id:
                item["progress_message_id"] = progress_message_id
            item["last_fingerprint"] = notification.fingerprint
            item["last_stage"] = notification.stage
            item["last_notified_at"] = utc_now()
            item["updated_at"] = utc_now()
            if key_event_sent:
                item["last_key_fingerprint"] = notification.fingerprint
                item["last_key_stage"] = notification.stage
            if notification.done:
                item["closed"] = True
                item["closed_at"] = utc_now()
            self.save()

    def append_action_audit(
        self,
        *,
        todo_id: str,
        action_id: str,
        actor_id: str,
        user_todo_id: str,
        decision_scope: dict[str, Any],
    ) -> None:
        with self.lock:
            item = self.data.setdefault("todos", {}).get(todo_id)
            if not isinstance(item, dict):
                return
            audit = item.setdefault("action_audit", [])
            if not isinstance(audit, list):
                audit = []
                item["action_audit"] = audit
            audit.append(
                {
                    "at": utc_now(),
                    "action_id": action_id,
                    "actor_id": actor_id,
                    "user_todo_id": user_todo_id,
                    "decision_scope": decision_scope,
                }
            )
            del audit[:-20]
            item["updated_at"] = utc_now()
            self.save()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return SENSITIVE_PARAM_RE.sub(r"\1[redacted]", value)


def log(event: str, **fields: Any) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    safe = {
        key: sanitize(value)
        for key, value in fields.items()
        if not any(marker in key.lower() for marker in ("secret", "token", "authorization"))
    }
    line = f"{utc_now()} {event} {json.dumps(safe, ensure_ascii=False, sort_keys=True)}\n"
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line)


def run_capture(args: list[str], *, cwd: Path = CONTROL_ROOT, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
    return subprocess.run(args, cwd=str(cwd), env=env, text=True, capture_output=True, timeout=timeout)


def run_text(args: list[str], *, cwd: Path = CONTROL_ROOT, timeout: float = 30) -> str:
    result = run_capture(args, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"{args[0]} exited {result.returncode}").strip())
    return result.stdout


def run_json(args: list[str], *, cwd: Path = CONTROL_ROOT, timeout: float = 45) -> dict[str, Any]:
    result = run_capture(args, cwd=cwd, timeout=timeout)
    parsed: Any = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except Exception:
            parsed = None
    if isinstance(parsed, dict):
        if result.returncode != 0:
            parsed["_cli_returncode"] = result.returncode
            parsed["_cli_stderr"] = compact_markdown(result.stderr, max_chars=600) if result.stderr else None
        return parsed
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"{args[0]} exited {result.returncode}").strip())
    raise RuntimeError(f"{args[0]} did not return JSON")


def reply_text(message_id: str, text: str) -> str:
    compact = compact_markdown(str(text or ""), max_chars=BOT_MAX_TEXT_CHARS, suffix="...")
    log("reply.text.start", message_id=message_id, chars=len(compact))
    out = run_text(["feishu-cli", "msg", "reply", message_id, "--text", compact], timeout=30)
    log("reply.text.ok", message_id=message_id)
    return out


def _send_card_command(args: list[str], card: dict[str, Any]) -> str:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(card, handle, ensure_ascii=False)
        card_path = Path(handle.name)
    try:
        return run_text([*args, "--msg-type", "interactive", "--content-file", str(card_path)], timeout=30)
    finally:
        try:
            card_path.unlink()
        except FileNotFoundError:
            pass


def reply_card(message_id: str, card: dict[str, Any]) -> str:
    log("reply.card.start", message_id=message_id)
    out = _send_card_command(["feishu-cli", "msg", "reply", message_id], card)
    log("reply.card.ok", message_id=message_id)
    return out


def update_card(message_id: str, card: dict[str, Any]) -> str:
    log("update.card.start", message_id=message_id)
    out = _send_card_command(["feishu-cli", "msg", "update", message_id], card)
    log("update.card.ok", message_id=message_id)
    return out


def card_for_notification(notification: ProgressNotification) -> dict[str, Any]:
    body = notification.markdown
    if notification.summary:
        body = f"**摘要**\n{notification.summary}\n\n{notification.markdown}"
    return build_lark_markdown_reply_card(
        body,
        title=notification.title,
        template=notification.template,
        footer=f"LoopX {notification.stage} | {notification.fingerprint}",
        actions=tuple(action.to_dict() for action in notification.actions),
    )


def reply_notification(message_id: str, notification: ProgressNotification) -> str:
    try:
        out = reply_card(message_id, card_for_notification(notification))
        return extract_reply_message_id(out, parent_message_id=message_id) or ""
    except Exception as exc:
        log("reply.card.error", message_id=message_id, error=str(exc))
        fallback = f"{notification.title}\n\n{notification.markdown}"
        out = reply_text(message_id, fallback)
        return extract_reply_message_id(out, parent_message_id=message_id) or ""


def publish_notification(
    *,
    state: StateStore,
    item: dict[str, Any],
    notification: ProgressNotification,
) -> None:
    original_message_id = str(item.get("message_id") or "")
    progress_message_id = str(item.get("progress_message_id") or "")
    stored_progress_message_id = progress_message_id
    key_event_sent = False
    card = card_for_notification(notification)
    if progress_message_id:
        try:
            update_card(progress_message_id, card)
        except Exception as exc:
            log(
                "update.card.error",
                message_id=progress_message_id,
                todo_id=notification.todo_id,
                error=str(exc),
            )
            replacement_id = reply_notification(original_message_id, notification)
            stored_progress_message_id = replacement_id or progress_message_id
    else:
        replacement_id = reply_notification(original_message_id, notification)
        stored_progress_message_id = replacement_id or ""

    should_send_key_event = (
        notification.key_event
        or notification.stage in KEY_EVENT_STAGES
        or notification.priority == "high"
        or notification.done
    )
    if (
        should_send_key_event
        and progress_message_id
        and item.get("last_key_fingerprint") != notification.fingerprint
    ):
        reply_notification(original_message_id, notification)
        key_event_sent = True
    elif should_send_key_event and not progress_message_id:
        key_event_sent = True

    state.update_after_notification(
        notification.todo_id,
        notification,
        progress_message_id=stored_progress_message_id,
        key_event_sent=key_event_sent,
    )


def extract_text(raw: dict[str, Any]) -> str:
    message = extract_message(raw)
    content = message.get("content") or ""
    try:
        return str(json.loads(content).get("text") or "").strip()
    except Exception:
        return str(content).strip()


def extract_message(raw: dict[str, Any]) -> dict[str, Any]:
    message = raw.get("event", {}).get("message") if isinstance(raw.get("event"), dict) else None
    if isinstance(message, dict):
        return message
    message = raw.get("message")
    return message if isinstance(message, dict) else {}


def extract_action_value(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        value = raw.get("value")
        action_id = raw.get("action_id")
        if isinstance(value, dict) and (value.get("source") == "loopx_feishu_progress_bridge" or value.get("action_id")):
            return value
        if action_id and raw.get("source") == "loopx_feishu_progress_bridge":
            return raw
        action = raw.get("action")
        if isinstance(action, dict):
            found = extract_action_value(action)
            if found:
                return found
        event = raw.get("event")
        if isinstance(event, dict):
            found = extract_action_value(event)
            if found:
                return found
        for child in raw.values():
            if isinstance(child, (dict, list)):
                found = extract_action_value(child)
                if found:
                    return found
    if isinstance(raw, list):
        for item in raw:
            found = extract_action_value(item)
            if found:
                return found
    return {}


def extract_actor_id(raw: Any) -> str:
    keys = ("open_id", "user_id", "union_id", "operator_id")
    if isinstance(raw, dict):
        for key in keys:
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:120]
        for container_key in ("operator", "user", "sender", "context"):
            value = raw.get(container_key)
            found = extract_actor_id(value)
            if found:
                return found
        for child in raw.values():
            if isinstance(child, (dict, list)):
                found = extract_actor_id(child)
                if found:
                    return found
    if isinstance(raw, list):
        for item in raw:
            found = extract_actor_id(item)
            if found:
                return found
    return ""


def loopx_status_payload() -> dict[str, Any]:
    return run_json(
        [
            LOOPX_BIN,
            "--registry",
            LOOPX_REGISTRY,
            "status",
            "--format",
            "json",
            "--agent-id",
            LOOPX_AGENT_ID,
        ],
        timeout=45,
    )


def loopx_quota_payload(goal_id: str) -> dict[str, Any]:
    return run_json(
        [
            LOOPX_BIN,
            "--registry",
            LOOPX_REGISTRY,
            "quota",
            "should-run",
            "--format",
            "json",
            "--goal-id",
            goal_id,
            "--agent-id",
            LOOPX_AGENT_ID,
        ],
        timeout=45,
    )


def add_loopx_todo(text: str, message_id: str) -> tuple[str, str, str]:
    args, clean, request_lane = build_feishu_request_todo_args(
        request_text=text,
        message_id=message_id,
        goal_id=LOOPX_GOAL_ID,
        agent_id=LOOPX_AGENT_ID,
    )
    out = run_text(
        [LOOPX_BIN, "--registry", LOOPX_REGISTRY, *args],
        timeout=30,
    )
    match = TODO_ID_RE.search(out)
    if not match:
        raise RuntimeError(f"LoopX did not return a todo id: {compact_markdown(out, max_chars=400, suffix='...')}")
    return match.group(0), clean, request_lane


def handle_text(text: str, message_id: str, state: StateStore) -> str | None:
    clean = str(text or "").strip()
    if not clean or clean in {"/help", "help"}:
        return bridge_help_text()
    if clean in {"/status", "status"}:
        return loopx_status_text(
            run_text=run_text,
            loopx_bin=LOOPX_BIN,
            registry=LOOPX_REGISTRY,
            agent_id=LOOPX_AGENT_ID,
            max_chars=BOT_MAX_TEXT_CHARS,
        )
    if clean in {"/plan", "plan"}:
        return loopx_scheduler_plan_text(
            run_json=run_json,
            loopx_bin=LOOPX_BIN,
            registry=LOOPX_REGISTRY,
            goal_id=LOOPX_GOAL_ID,
            agent_id=LOOPX_AGENT_ID,
            max_chars=BOT_MAX_TEXT_CHARS,
        )
    if clean in {"/next", "next"}:
        return loopx_scheduler_next_batch_text(
            run_json=run_json,
            loopx_bin=LOOPX_BIN,
            registry=LOOPX_REGISTRY,
            goal_id=LOOPX_GOAL_ID,
            agent_id="",
            max_chars=BOT_MAX_TEXT_CHARS,
        )
    if clean in {"/check", "check"}:
        return loopx_check_text(
            run_text=run_text,
            loopx_bin=LOOPX_BIN,
            registry=LOOPX_REGISTRY,
            control_root=CONTROL_ROOT,
            max_chars=BOT_MAX_TEXT_CHARS,
        )
    request_text = clean[len("/ask ") :].strip() if clean.startswith("/ask ") else clean
    todo_id, normalized_request, request_lane = add_loopx_todo(request_text, message_id)
    notification = build_acceptance_notification(
        todo_id=todo_id,
        goal_id=LOOPX_GOAL_ID,
        request_text=normalized_request,
        agent_id=LOOPX_AGENT_ID,
    )
    state.track_todo(
        todo_id=todo_id,
        message_id=message_id,
        request_text=normalized_request,
        goal_id=LOOPX_GOAL_ID,
        agent_id=LOOPX_AGENT_ID,
        request_lane=request_lane,
        initial_fingerprint=notification.fingerprint,
    )
    publish_notification(state=state, item=state.todo(todo_id), notification=notification)
    return None


def run_todo_lifecycle_command(args: list[str]) -> str:
    return run_text([LOOPX_BIN, "--registry", LOOPX_REGISTRY, "todo", *args], timeout=30)


def handle_card_action(raw: dict[str, Any], state: StateStore) -> bool:
    value = extract_action_value(raw)
    if not value:
        return False
    action_id = str(value.get("action_id") or value.get("decision") or "").strip()
    goal_id = str(value.get("goal_id") or LOOPX_GOAL_ID)
    todo_id = str(value.get("todo_id") or "")
    user_todo_id = str(value.get("user_todo_id") or "")
    decision_scope = value.get("decision_scope") if isinstance(value.get("decision_scope"), dict) else {}
    actor_id = extract_actor_id(raw)
    item = state.todo(todo_id)
    original_message_id = str(item.get("message_id") or extract_message(raw).get("message_id") or "")
    log(
        "card.action.received",
        action_id=action_id,
        goal_id=goal_id,
        todo_id=todo_id,
        user_todo_id=user_todo_id,
        actor_id=actor_id,
        decision_scope=decision_scope,
    )
    commands, response = todo_commands_for_action(
        action_id=action_id,
        goal_id=goal_id,
        todo_id=todo_id,
        user_todo_id=user_todo_id,
        actor_id=actor_id,
        decision_scope=decision_scope,
    )
    for command in commands:
        run_todo_lifecycle_command(command)
    if commands:
        state.append_action_audit(
            todo_id=todo_id,
            action_id=action_id,
            actor_id=actor_id,
            user_todo_id=user_todo_id,
            decision_scope=decision_scope,
        )
    if not commands:
        log("card.action.skip", reason=response)
    if original_message_id:
        reply_text(original_message_id, response)
    return True


def handle_event(raw: dict[str, Any], state: StateStore) -> None:
    try:
        if handle_card_action(raw, state):
            return
    except Exception as exc:
        log("card.action.error", error=str(exc))
        message_id = str(extract_message(raw).get("message_id") or "")
        if message_id:
            reply_text(message_id, f"LoopX button action failed: {exc}")
        return
    message = extract_message(raw)
    message_id = str(message.get("message_id") or "")
    log(
        "event.received",
        event_type=raw.get("header", {}).get("event_type") if isinstance(raw.get("header"), dict) else raw.get("schema"),
        message_id=message_id,
        chat_type=message.get("chat_type"),
    )
    if not message_id:
        log("event.skip", reason="missing_message_id")
        return
    text = extract_text(raw)
    log("event.text", message_id=message_id, chars=len(text), command=(text.split() or [""])[0])
    try:
        response = handle_text(text, message_id, state)
        if response:
            reply_text(message_id, response)
    except Exception as exc:
        log("event.error", message_id=message_id, error=str(exc))
        reply_text(message_id, f"LoopX bridge failed: {exc}")


def poll_progress_once(state: StateStore) -> int:
    active = state.active_todos()
    if not active:
        return 0
    sent = 0
    try:
        status_payload = loopx_status_payload()
    except Exception as exc:
        log("progress.status.error", error=str(exc), active=len(active))
        for item in active:
            notification = build_bridge_error_notification(
                todo_id=str(item.get("todo_id") or ""),
                goal_id=str(item.get("goal_id") or LOOPX_GOAL_ID),
                source="status",
                error=exc,
            )
            if should_emit_notification(notification, previous_fingerprint=item.get("last_fingerprint")):
                publish_notification(state=state, item=item, notification=notification)
                sent += 1
        return sent
    for item in active:
        todo_id = str(item.get("todo_id") or "")
        message_id = str(item.get("message_id") or "")
        goal_id = str(item.get("goal_id") or LOOPX_GOAL_ID)
        if not todo_id or not message_id:
            continue
        try:
            quota_payload = loopx_quota_payload(goal_id)
            notification = build_progress_notification(
                todo_id=todo_id,
                goal_id=goal_id,
                status_payload=status_payload,
                quota_payload=quota_payload,
                request_text=item.get("request_text"),
            )
        except Exception as exc:
            log("progress.quota.error", todo_id=todo_id, goal_id=goal_id, error=str(exc))
            notification = build_bridge_error_notification(
                todo_id=todo_id,
                goal_id=goal_id,
                source="quota",
                error=exc,
            )
        if not should_emit_notification(notification, previous_fingerprint=item.get("last_fingerprint")):
            continue
        publish_notification(state=state, item=item, notification=notification)
        sent += 1
    return sent


def progress_loop(state: StateStore, stop_event: threading.Event) -> None:
    log("progress.loop.start", poll_seconds=POLL_SECONDS)
    while not stop_event.wait(POLL_SECONDS):
        try:
            sent = poll_progress_once(state)
            log("progress.poll.ok", sent=sent)
        except Exception as exc:
            log("progress.poll.error", error=str(exc))


def consume_event_stream(
    event_type: str,
    state: StateStore,
    stop_event: threading.Event,
    exit_codes: list[int],
    *,
    primary_event_type: str,
) -> None:
    proc = subprocess.Popen(
        ["feishu-cli", "event", "consume", event_type],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env={**os.environ, "PATH": f"{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")},
    )
    log("consumer.start", event_type=event_type, pid=proc.pid)

    def stderr_reader() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            log("consumer.stderr", event_type=event_type, line=line.strip()[:500])

    threading.Thread(target=stderr_reader, daemon=True).start()
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if stop_event.is_set():
                break
            line = line.strip()
            if not line:
                continue
            try:
                handle_event(json.loads(line), state)
            except Exception as exc:
                log("event.parse_error", event_type=event_type, error=str(exc), sample=line[:160])
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
    code = proc.wait()
    exit_codes.append(code)
    if event_type == primary_event_type or code == 0:
        stop_event.set()
    log("consumer.close", event_type=event_type, code=code)


def consume_forever(state: StateStore) -> int:
    log(
        "process.start",
        goal=LOOPX_GOAL_ID,
        agent=LOOPX_AGENT_ID,
        control_root=str(CONTROL_ROOT),
        event_types=",".join(EVENT_TYPES),
    )
    stop_event = threading.Event()
    progress_thread = threading.Thread(target=progress_loop, args=(state, stop_event), daemon=True)
    progress_thread.start()
    exit_codes: list[int] = []
    primary_event_type = EVENT_TYPES[0] if EVENT_TYPES else "im.message.receive_v1"
    threads = [
        threading.Thread(
            target=consume_event_stream,
            args=(event_type, state, stop_event, exit_codes),
            kwargs={"primary_event_type": primary_event_type},
            daemon=True,
        )
        for event_type in EVENT_TYPES
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    stop_event.set()
    return next((code for code in exit_codes if code), 0)


def bridge_doctor(state: StateStore) -> dict[str, Any]:
    path_env = f"{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")
    loopx_path = shutil.which(LOOPX_BIN, path=path_env)
    feishu_path = shutil.which("feishu-cli", path=path_env)
    active = state.active_todos()
    payload: dict[str, Any] = {
        "ok": bool(loopx_path and feishu_path),
        "schema_version": "loopx_feishu_progress_bridge_doctor_v1",
        "control_root": str(CONTROL_ROOT),
        "registry": LOOPX_REGISTRY,
        "goal_id": LOOPX_GOAL_ID,
        "agent_id": LOOPX_AGENT_ID,
        "state_file": str(STATE_FILE),
        "state_schema": state.data.get("schema_version"),
        "tracked_active_todos": len(active),
        "tracked_total_todos": len(state.data.get("todos", {})) if isinstance(state.data.get("todos"), dict) else 0,
        "log_file": str(LOG_FILE),
        "poll_seconds": POLL_SECONDS,
        "event_types": list(EVENT_TYPES),
        "loopx_bin": loopx_path,
        "feishu_cli": feishu_path,
        "main_card_mode": "update_existing_reply_then_reply_fallback",
        "key_event_mode": "separate_reply_for_user_action_blocked_done_or_bridge_error",
        "launch_agent_label": DEFAULT_LAUNCH_AGENT_LABEL,
        "problems": [],
    }
    problems = payload["problems"]
    if not loopx_path:
        problems.append(f"LoopX binary not found: {LOOPX_BIN}")
    if not feishu_path:
        problems.append("feishu-cli not found in PATH")
    if not CONTROL_ROOT.exists():
        problems.append(f"control root does not exist: {CONTROL_ROOT}")
    if not active:
        payload["status"] = "ready_no_active_tracked_todos" if payload["ok"] else "blocked"
    else:
        payload["status"] = "ready_with_active_tracked_todos" if payload["ok"] else "blocked"
    payload["ok"] = payload["ok"] and not problems
    return payload


def render_doctor_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Feishu Progress Bridge Doctor",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- status: `{payload.get('status')}`",
        f"- control_root: `{payload.get('control_root')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- state_file: `{payload.get('state_file')}`",
        f"- tracked_active_todos: `{payload.get('tracked_active_todos')}`",
        f"- loopx_bin: `{payload.get('loopx_bin')}`",
        f"- feishu_cli: `{payload.get('feishu_cli')}`",
        f"- event_types: `{','.join(payload.get('event_types') or [])}`",
        f"- launch_agent_label: `{payload.get('launch_agent_label')}`",
    ]
    problems = payload.get("problems") if isinstance(payload.get("problems"), list) else []
    if problems:
        lines.extend(["", "## Problems"])
        lines.extend(f"- {problem}" for problem in problems)
    return "\n".join(lines)


def launch_agent_plist(label: str = DEFAULT_LAUNCH_AGENT_LABEL) -> bytes:
    environment = {
        "LOOPX_CONTROL_ROOT": str(CONTROL_ROOT),
        "LOOPX_BIN": LOOPX_BIN,
        "LOOPX_REGISTRY": LOOPX_REGISTRY,
        "LOOPX_GOAL_ID": LOOPX_GOAL_ID,
        "LOOPX_AGENT_ID": LOOPX_AGENT_ID,
        "LOOPX_FEISHU_PROGRESS_POLL_SECONDS": str(POLL_SECONDS),
        "LOOPX_FEISHU_PROGRESS_STATE": str(STATE_FILE),
        "LOOPX_FEISHU_PROGRESS_LOG": str(LOG_FILE),
        "LOOPX_FEISHU_EVENT_TYPES": ",".join(EVENT_TYPES),
    }
    payload = {
        "Label": label,
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve())],
        "WorkingDirectory": str(CONTROL_ROOT),
        "EnvironmentVariables": environment,
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": str(LOG_FILE.with_suffix(".stdout.log")),
        "StandardErrorPath": str(LOG_FILE.with_suffix(".stderr.log")),
        "ThrottleInterval": 10,
    }
    return plistlib.dumps(payload, sort_keys=True)


def tail_log(lines: int) -> str:
    if not LOG_FILE.exists():
        return ""
    content = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-max(0, lines) :])


def self_test() -> int:
    state = StateStore(Path(tempfile.mkdtemp()) / "state.json")
    event = {"event": {"message": {"message_id": "om_test", "content": json.dumps({"text": "/help"})}}}
    assert extract_text(event) == "/help"
    assert "/plan" in bridge_help_text()
    assert "/next" in bridge_help_text()
    state.track_todo(
        todo_id="todo_test",
        message_id="om_test",
        request_text="do bounded work",
        goal_id="goal",
        agent_id="agent",
    )
    assert state.active_todos()[0]["todo_id"] == "todo_test"
    notification = build_acceptance_notification(
        todo_id="todo_test",
        goal_id="goal",
        request_text="do bounded work",
        agent_id="agent",
    )
    card = card_for_notification(notification)
    assert card["header"]["template"] == "green"
    assert card["elements"][0]["text"]["content"]
    action_event = {
        "event": {
            "action": {
                "value": {
                    "source": "loopx_feishu_progress_bridge",
                    "action_id": "approve_continue",
                    "todo_id": "todo_test",
                    "goal_id": "goal",
                    "user_todo_id": "todo_user_gate",
                }
            }
        }
    }
    assert extract_action_value(action_event)["action_id"] == "approve_continue"
    commands, response = todo_commands_for_action(
        action_id="approve_continue",
        goal_id="goal",
        todo_id="todo_test",
        user_todo_id="todo_user_gate",
    )
    assert commands[0][:6] == ["complete", "--goal-id", "goal", "--role", "user", "--todo-id"]
    assert "批准继续" in response
    assert loopx_scheduler_next_batch_text(
        run_json=lambda args, timeout: {"dispatch_mode": "idle"},
        loopx_bin="loopx",
        registry="registry",
        goal_id="goal",
        agent_id="agent",
        max_chars=80,
    )
    doctor = bridge_doctor(state)
    assert doctor["state_schema"] == STATE_SCHEMA_VERSION
    assert b"KeepAlive" in launch_agent_plist()
    print("feishu loopx progress bridge self-test ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Feishu/Lark event bridge with LoopX progress cards.")
    parser.add_argument("--self-test", action="store_true", help="Run local parser/state/card checks.")
    parser.add_argument("--progress-once", action="store_true", help="Poll tracked todos once and exit.")
    parser.add_argument("--doctor", action="store_true", help="Inspect bridge runtime readiness and tracked state.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format for --doctor.")
    parser.add_argument("--print-launch-agent", action="store_true", help="Print a macOS launchd plist for this bridge.")
    parser.add_argument("--migrate-state", action="store_true", help="Rewrite the state file using the current schema.")
    parser.add_argument("--log-tail", type=int, help="Print the last N bridge log lines and exit.")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    state = StateStore(STATE_FILE)
    if args.migrate_state:
        state.save()
        print(f"migrated {STATE_FILE} to {STATE_SCHEMA_VERSION}")
        return 0
    if args.doctor:
        payload = bridge_doctor(state)
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(render_doctor_markdown(payload))
        return 0 if payload.get("ok") else 1
    if args.print_launch_agent:
        sys.stdout.buffer.write(launch_agent_plist())
        return 0
    if args.log_tail is not None:
        print(tail_log(args.log_tail))
        return 0
    if args.progress_once:
        return 0 if poll_progress_once(state) >= 0 else 1
    return consume_forever(state)


if __name__ == "__main__":
    raise SystemExit(main())
