"""Read-only completed-task readback owned by the Chat HTTP surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .todos import list_goal_todos

CHAT_COMPLETED_TODOS_PATH = "/api/chat/todos/completed"
COMPLETED_TODOS_SCOPE = "active_completed_advancement"
COMPLETED_TODOS_DEFAULT_LIMIT = 50
COMPLETED_TODOS_MAX_LIMIT = 100
_ALLOWED_QUERY_KEYS = frozenset({"goal_id", "agent_id", "offset", "limit"})


class ChatCompletedTodosRequestMixin:
    """Serve a bounded, goal-scoped page of completed agent advancement tasks.

    The page is a projection of the existing todo read contract: only active,
    completed `advancement_task` records are listed, archived work and
    continuous monitors are excluded, evidence is dropped, and every item is
    redacted through the handler's compact-todo hook. No task state is written.
    """

    path: str
    server: Any

    def _send_error(self, message: str, **kwargs: Any) -> None:
        raise NotImplementedError

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        raise NotImplementedError

    def _compact_todo_record(self, item: dict[str, object], *, protected_paths: list[Path]) -> dict[str, object]:
        raise NotImplementedError

    def _completed_todos(self) -> None:
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if set(query) - _ALLOWED_QUERY_KEYS or any(len(values) != 1 for values in query.values()):
            self._send_error("invalid completed task query")
            return
        goal_id = query.get("goal_id", [""])[0].strip()
        agent_id = query.get("agent_id", [""])[0].strip() or None
        try:
            offset = int(query.get("offset", ["0"])[0])
            limit = int(query.get("limit", [str(COMPLETED_TODOS_DEFAULT_LIMIT)])[0])
            if not goal_id or offset < 0 or not 1 <= limit <= COMPLETED_TODOS_MAX_LIMIT:
                raise ValueError
        except ValueError:
            self._send_error(
                f"goal_id, offset >= 0 and limit between 1 and {COMPLETED_TODOS_MAX_LIMIT} are required"
            )
            return
        if self.server.selected_goal_id and goal_id != self.server.selected_goal_id:
            self._send_error("Goal is outside this server scope", status=403)
            return
        try:
            result = list_goal_todos(
                registry_path=self.server.registry_path,
                goal_id=goal_id,
                role="agent",
                status="done",
                agent_id=agent_id,
                runtime_root_arg=self.server.runtime_root_override,
            )
        except ValueError:
            self._send_error("Goal or task source is unavailable", status=404)
            return
        except OSError:
            self._send_error("Task source could not be read", status=503)
            return
        items = sorted(
            [
                item
                for item in result.get("todos", [])
                if item.get("task_class") == "advancement_task"
                and item.get("archive_state", "active") == "active"
                and item.get("done") is True
                and item.get("todo_id")
            ],
            key=lambda item: (str(item.get("completed_at") or ""), str(item.get("todo_id") or "")),
            reverse=True,
        )
        protected_paths = [Path(result[key]) for key in ("state_file", "project") if result.get(key)]
        page = []
        for item in items[offset : offset + limit]:
            compact = self._compact_todo_record(item, protected_paths=protected_paths)
            compact.pop("evidence", None)
            compact["text"] = compact.get("text") or ""
            page.append(compact)
        self._send_json(
            {
                "ok": True,
                "goal_id": goal_id,
                "scope": COMPLETED_TODOS_SCOPE,
                "total": len(items),
                "items": page,
                "next_offset": offset + len(page) if offset + len(page) < len(items) else None,
            }
        )
