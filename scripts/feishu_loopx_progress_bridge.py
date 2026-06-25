#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
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

from loopx.capabilities.lark.message_card import build_lark_markdown_reply_card, compact_markdown
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
SENSITIVE_PARAM_RE = re.compile(
    r"((?:access_key|authorization|secret|ticket|token|tenant_access_token|app_access_token|refresh_token)=)[^&\s]+",
    re.IGNORECASE,
)
TODO_ID_RE = re.compile(r"\btodo_[A-Za-z0-9_]+\b")


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": "loopx_feishu_progress_bridge_state_v1", "todos": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        todos = data.get("todos")
        if not isinstance(todos, dict):
            todos = {}
        data["schema_version"] = "loopx_feishu_progress_bridge_state_v1"
        data["todos"] = todos
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
                "created_at": previous.get("created_at") or now,
                "updated_at": now,
                "closed": bool(previous.get("closed", False)),
                "last_fingerprint": initial_fingerprint or previous.get("last_fingerprint"),
                "last_stage": previous.get("last_stage"),
            }
            self.save()

    def active_todos(self) -> list[dict[str, Any]]:
        with self.lock:
            todos = self.data.get("todos") if isinstance(self.data.get("todos"), dict) else {}
            return [
                dict(item)
                for item in todos.values()
                if isinstance(item, dict) and not item.get("closed") and item.get("message_id")
            ]

    def update_after_notification(self, todo_id: str, notification: ProgressNotification) -> None:
        with self.lock:
            todos = self.data.setdefault("todos", {})
            item = todos.get(todo_id)
            if not isinstance(item, dict):
                return
            item["last_fingerprint"] = notification.fingerprint
            item["last_stage"] = notification.stage
            item["last_notified_at"] = utc_now()
            item["updated_at"] = utc_now()
            if notification.done:
                item["closed"] = True
                item["closed_at"] = utc_now()
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


def reply_text(message_id: str, text: str) -> None:
    compact = compact_markdown(str(text or ""), max_chars=BOT_MAX_TEXT_CHARS, suffix="...")
    log("reply.text.start", message_id=message_id, chars=len(compact))
    run_text(["feishu-cli", "msg", "reply", message_id, "--text", compact], timeout=30)
    log("reply.text.ok", message_id=message_id)


def reply_card(message_id: str, card: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(card, handle, ensure_ascii=False)
        card_path = Path(handle.name)
    try:
        log("reply.card.start", message_id=message_id, card_file=str(card_path))
        run_text(
            [
                "feishu-cli",
                "msg",
                "reply",
                message_id,
                "--msg-type",
                "interactive",
                "--content-file",
                str(card_path),
            ],
            timeout=30,
        )
        log("reply.card.ok", message_id=message_id)
    finally:
        try:
            card_path.unlink()
        except FileNotFoundError:
            pass


def card_for_notification(notification: ProgressNotification) -> dict[str, Any]:
    return build_lark_markdown_reply_card(
        notification.markdown,
        title=notification.title,
        template=notification.template,
        footer=f"LoopX {notification.stage} | {notification.fingerprint}",
    )


def reply_notification(message_id: str, notification: ProgressNotification) -> None:
    try:
        reply_card(message_id, card_for_notification(notification))
    except Exception as exc:
        log("reply.card.error", message_id=message_id, error=str(exc))
        fallback = f"{notification.title}\n\n{notification.markdown}"
        reply_text(message_id, fallback)


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


def help_text() -> str:
    return "\n".join(
        [
            "LoopX Feishu bridge.",
            "",
            "Commands:",
            "/help - show this message",
            "/status - show compact LoopX status",
            "/check - run LoopX boundary check",
            "/ask <task> - create a LoopX todo and receive progress cards",
        ]
    )


def loopx_status_text() -> str:
    out = run_text([LOOPX_BIN, "--registry", LOOPX_REGISTRY, "status", "--agent-id", LOOPX_AGENT_ID], timeout=30)
    interesting: list[str] = []
    for line in out.splitlines():
        if (
            line.startswith("- ok:")
            or "Attention Queue" in line
            or "waiting_on=" in line
            or "next_agent_todo" in line
            or "next_user_todo" in line
            or "quota:" in line
            or "action:" in line
            or "status=" in line
        ):
            interesting.append(line)
    return compact_markdown("\n".join(interesting) or out, max_chars=BOT_MAX_TEXT_CHARS, suffix="...")


def loopx_check_text() -> str:
    return compact_markdown(
        run_text([LOOPX_BIN, "--registry", LOOPX_REGISTRY, "check", "--scan-root", str(CONTROL_ROOT)], timeout=30),
        max_chars=BOT_MAX_TEXT_CHARS,
        suffix="...",
    )


def loopx_status_payload() -> dict[str, Any]:
    return run_json(
        [
            LOOPX_BIN,
            "--registry",
            LOOPX_REGISTRY,
            "--format",
            "json",
            "status",
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
            "--format",
            "json",
            "quota",
            "should-run",
            "--goal-id",
            goal_id,
            "--agent-id",
            LOOPX_AGENT_ID,
        ],
        timeout=45,
    )


def add_loopx_todo(text: str, message_id: str) -> tuple[str, str]:
    clean = " ".join(compact_markdown(text, max_chars=700, suffix="...").split())
    if not clean:
        raise ValueError("Write a task after /ask.")
    todo_text = f"Handle Feishu bot request and reply to message_id={message_id} when done. Request: {clean}"
    out = run_text(
        [
            LOOPX_BIN,
            "--registry",
            LOOPX_REGISTRY,
            "todo",
            "add",
            "--goal-id",
            LOOPX_GOAL_ID,
            "--role",
            "agent",
            "--text",
            todo_text,
            "--task-class",
            "advancement_task",
            "--action-kind",
            "feishu_user_request",
            "--claimed-by",
            LOOPX_AGENT_ID,
        ],
        timeout=30,
    )
    match = TODO_ID_RE.search(out)
    if not match:
        raise RuntimeError(f"LoopX did not return a todo id: {compact_markdown(out, max_chars=400, suffix='...')}")
    return match.group(0), clean


def handle_text(text: str, message_id: str, state: StateStore) -> str | None:
    clean = str(text or "").strip()
    if not clean or clean in {"/help", "help"}:
        return help_text()
    if clean in {"/status", "status"}:
        return loopx_status_text()
    if clean in {"/check", "check"}:
        return loopx_check_text()
    request_text = clean[len("/ask ") :].strip() if clean.startswith("/ask ") else clean
    todo_id, normalized_request = add_loopx_todo(request_text, message_id)
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
        initial_fingerprint=notification.fingerprint,
    )
    reply_notification(message_id, notification)
    state.update_after_notification(todo_id, notification)
    return None


def handle_event(raw: dict[str, Any], state: StateStore) -> None:
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
                reply_notification(str(item.get("message_id") or ""), notification)
                state.update_after_notification(notification.todo_id, notification)
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
        reply_notification(message_id, notification)
        state.update_after_notification(todo_id, notification)
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


def consume_forever(state: StateStore) -> int:
    log("process.start", goal=LOOPX_GOAL_ID, agent=LOOPX_AGENT_ID, control_root=str(CONTROL_ROOT))
    stop_event = threading.Event()
    thread = threading.Thread(target=progress_loop, args=(state, stop_event), daemon=True)
    thread.start()
    proc = subprocess.Popen(
        ["feishu-cli", "event", "consume", "im.message.receive_v1"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env={**os.environ, "PATH": f"{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")},
    )
    log("consumer.start", pid=proc.pid)

    def stderr_reader() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            log("consumer.stderr", line=line.strip()[:500])

    threading.Thread(target=stderr_reader, daemon=True).start()
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                handle_event(json.loads(line), state)
            except Exception as exc:
                log("event.parse_error", error=str(exc), sample=line[:160])
    finally:
        stop_event.set()
    code = proc.wait()
    log("consumer.close", code=code)
    return code


def self_test() -> int:
    state = StateStore(Path(tempfile.mkdtemp()) / "state.json")
    event = {"event": {"message": {"message_id": "om_test", "content": json.dumps({"text": "/help"})}}}
    assert extract_text(event) == "/help"
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
    print("feishu loopx progress bridge self-test ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Feishu/Lark event bridge with LoopX progress cards.")
    parser.add_argument("--self-test", action="store_true", help="Run local parser/state/card checks.")
    parser.add_argument("--progress-once", action="store_true", help="Poll tracked todos once and exit.")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    state = StateStore(STATE_FILE)
    if args.progress_once:
        return 0 if poll_progress_once(state) >= 0 else 1
    return consume_forever(state)


if __name__ == "__main__":
    raise SystemExit(main())
