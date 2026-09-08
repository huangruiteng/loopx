"""Typed action orchestration for the owner-local LoopX Chat control plane."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .agent_registry import agent_profile_for_goal, registered_agent_ids_for_goal
from .bootstrap import bootstrap_project
from .chat import apply_todo_review_preview, build_todo_review_preview
from .chat_action_store import ActionConflictError, ChatActionStore
from .chat_goal_lifecycle_actions import ChatGoalLifecycleActionMixin
from .chat_monitor_actions import ChatMonitorActionMixin
from .chat_store import ChatSessionStore
from .chat_todo_actions import ChatTodoActionMixin
from .configure_goal import configure_goal
from .control_plane.runtime.time import now_utc, parse_timestamp, utc_isoformat
from .control_plane.scheduler.monitor_todo import monitor_next_due_at
from .control_plane.todos.contract import require_supported_todo_resume_when
from .history import load_registry
from .host_loop_activation import build_host_loop_activation_packet
from .kiro_cli_goal_mode import KIRO_CLI_CHAT_AGENT_ID
from .quota import build_quota_should_run
from .registry import registry_goals
from .todos import add_goal_todo, update_goal_todo


CHAT_ACTION_RESPONSE_SCHEMA_VERSION = "loopx_chat_action_response_v1"
SUPPORTED_ACTION_KINDS = {
    "todo.create",
    "todo.update",
    "run.correct",
    "goal.create",
    "goal.update",
    "goal.lifecycle",
    "agent.bind",
    "heartbeat.bind",
    "monitor.create",
    "monitor.update",
    "gate.resolve",
}
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
# Runtime Endpoint ids and durable Goal agent ids are chosen independently, so
# a family token collapses both onto the host that produced them: Endpoint
# `codex` has to resolve to a registered `codex-main-control`. Every host that
# owns a built-in Endpoint needs a row here, or selecting it in the workspace
# raises `agent_binding_required` for an agent the user did register. A host
# absent from the table resolves to its own id, which only matches an
# identically named agent — correct as a fallback, wrong as a built-in's only
# behavior. Matching is bounded at a `-` delimiter, so this table lists family
# roots rather than free prefixes: `kiro-worker-1` joins the Kiro family while
# `kiroscope-worker` keeps its own identity. Keep the rule in this one table.
_AGENT_FAMILY_ROOTS: tuple[tuple[str, str], ...] = (
    ("codex", "codex"),
    ("claude", "claude-code"),
    ("kiro", KIRO_CLI_CHAT_AGENT_ID),
)
_MONITOR_CADENCE = re.compile(
    r"^(?P<count>[1-9][0-9]{0,4})(?P<unit>s|m|h|d)$",
    re.IGNORECASE,
)


class ProtectedActionGate(ActionConflictError):
    """A typed preview is valid while its canonical write needs an explicit gate."""

    def __init__(self, action_kind: str, *, gate: Mapping[str, Any] | None = None) -> None:
        self.action_kind = action_kind
        self.gate = dict(gate or {
            "kind": "protected_action",
            "summary": f"{action_kind} needs an explicit canonical LoopX write service.",
            "next_action": "Keep this preview and complete the protected transition through its canonical LoopX service.",
        })
        self.proposal: dict[str, Any] | None = None
        super().__init__(self.gate["summary"])


def _opaque(value: Any, *, field: str) -> str:
    token = str(value or "").strip()
    if not _OPAQUE_ID.fullmatch(token):
        raise ValueError(f"{field} must be a compact opaque id")
    return token


def _text(value: Any, *, field: str, limit: int = 1000) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text or len(text) > limit:
        raise ValueError(f"{field} must be bounded visible text")
    return text


def _digest(payload: Any) -> str:
    stable = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _normalize_cadence(value: Any) -> str:
    candidate = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "hourly": "1h",
        "daily": "1d",
        "every_hour": "1h",
        "every_day": "1d",
    }
    if candidate in aliases:
        return aliases[candidate]
    verbose = re.fullmatch(
        r"every_(?P<count>[1-9][0-9]{0,4})_(?P<unit>seconds?|minutes?|hours?|days?)",
        candidate,
    )
    if verbose:
        units = {"s": "s", "m": "m", "h": "h", "d": "d"}
        return f"{verbose.group('count')}{units[verbose.group('unit')[0]]}"
    compact = candidate.replace(" ", "")
    match = _MONITOR_CADENCE.fullmatch(compact)
    if match:
        return f"{int(match.group('count'))}{match.group('unit').lower()}"
    raise ValueError("cadence must look like 30m, 2h, 1d, hourly, or daily")


def _monitor_metadata(parameters: Mapping[str, Any]) -> dict[str, str]:
    metadata = {
        key: str(parameters[key])
        for key in ("target_key", "cadence")
        if parameters.get(key)
    }
    cadence = metadata.get("cadence")
    if cadence:
        next_due_at = monitor_next_due_at(
            generated_at=now_utc().isoformat(),
            cadence=cadence,
        )
        if next_due_at:
            metadata["next_due_at"] = next_due_at
    stop_condition = str(parameters.get("stop_condition") or "").strip()
    if stop_condition:
        if parse_timestamp(stop_condition) is not None:
            metadata["expires_at"] = stop_condition
        elif stop_condition.lower() in {"watch_only", "watch-only", "watch", "continuous", "never"}:
            metadata["watch_only"] = "true"
    return metadata


def _monitor_text(parameters: Mapping[str, Any]) -> str | None:
    target = str(parameters.get("target") or "").strip()
    stop_condition = str(parameters.get("stop_condition") or "").strip()
    if target and stop_condition:
        return f"{target} (stop when {stop_condition})"
    if target:
        return target
    if stop_condition:
        return f"Monitor until {stop_condition}"
    return None


class ChatActionService(
    ChatGoalLifecycleActionMixin, ChatMonitorActionMixin, ChatTodoActionMixin
):
    """Validate previews and route applies through canonical LoopX services."""

    def __init__(
        self,
        *,
        store: ChatActionStore,
        registry_path: Path,
        chat_store: ChatSessionStore | None = None,
        runtime_controller: Any | None = None,
        workspace_roots: Sequence[Path] = (),
    ) -> None:
        self.store = store
        self.registry_path = Path(registry_path).expanduser().resolve()
        self.chat_store = chat_store
        self.runtime_controller = runtime_controller
        self.workspace_roots = tuple(
            Path(root).expanduser().resolve() for root in workspace_roots
        )

    def _registry(self) -> dict[str, Any]:
        return load_registry(self.registry_path)

    def _goal(self, goal_id: str) -> dict[str, Any]:
        goal = next(
            (goal for goal in registry_goals(self._registry()) if str(goal.get("id") or "") == goal_id),
            None,
        )
        if goal is None:
            raise ValueError("goal_id was not found in the active LoopX registry")
        return goal

    def _registry_fingerprint(self) -> str:
        try:
            content = self.registry_path.read_bytes()
        except OSError as exc:
            raise ValueError("the active LoopX registry is unavailable") from exc
        return hashlib.sha256(content).hexdigest()

    def _agent_eligibility(
        self,
        agent_id: str,
        *,
        project: Path | None = None,
        requires_tools: bool = True,
    ) -> dict[str, Any]:
        if self.runtime_controller is None:
            return {
                "agent_id": agent_id,
                "available": True,
                "tool_calls": True,
                "trust_scope": "read_only",
                "source": "configuration_only",
            }
        capabilities = self.runtime_controller.capabilities()
        row = next(
            (
                item
                for item in capabilities
                if isinstance(item, Mapping) and str(item.get("agent_id") or "") == agent_id
            ),
            None,
        )
        if row is None:
            raise ValueError("selected Agent endpoint is not registered")
        if row.get("available") is not True:
            raise ValueError("selected Agent endpoint is not healthy")
        if requires_tools and row.get("tool_calls") is not True:
            raise ValueError("selected Agent endpoint cannot execute Goal tools")
        if str(row.get("trust_scope") or "") not in {"read_only", "workspace_write"}:
            raise ValueError("selected Agent endpoint has an incompatible trust scope")
        endpoint_registry = getattr(self.runtime_controller, "endpoint_registry", None)
        endpoint = endpoint_registry.get(agent_id) if endpoint_registry is not None else None
        if endpoint is not None and project is not None and endpoint.location == "remote":
            mapped = endpoint.mapped_work_dir(project)
            if mapped == project and not endpoint.workspace_mapping:
                raise ValueError("remote Agent endpoint needs a workspace mapping")
        return dict(row)

    @staticmethod
    def _agent_family(value: str) -> str:
        """Classify an id into a host family, bounded at a delimiter.

        A bare prefix match silently swallowed unrelated operator ids:
        ``kiroscope-worker`` and ``codexplorer`` are not the Kiro or Codex
        family, but they matched, and a single false match is enough for
        ``_resolve_goal_agent`` to bind a built-in endpoint to the wrong
        durable identity instead of raising ``agent_binding_required``. The
        family token must therefore be the whole id or end at a ``-``
        delimiter, which still accepts every documented shape (``kiro``,
        ``kiro-cli``, ``kiro-worker-1``) because ids are normalized first.
        """
        token = value.strip().lower().replace("_", "-")
        for prefix, family in _AGENT_FAMILY_ROOTS:
            if token == prefix or token.startswith(f"{prefix}-"):
                return family
        return token

    def _resolve_goal_agent(self, goal_id: str, endpoint_id: str) -> str:
        """Resolve a runtime Endpoint to the Goal's durable peer identity."""

        self._agent_eligibility(endpoint_id)
        goal = self._goal(goal_id)
        registered = registered_agent_ids_for_goal(goal)
        if endpoint_id in registered:
            return endpoint_id
        endpoint_family = self._agent_family(endpoint_id)
        matches: list[str] = []
        for agent_id in registered:
            profile = agent_profile_for_goal(goal, agent_id) or {}
            aliases = {
                agent_id,
                str(profile.get("endpoint_id") or ""),
                str(profile.get("adapter_kind") or ""),
                str(profile.get("provider") or ""),
            }
            if any(self._agent_family(alias) == endpoint_family for alias in aliases if alias):
                matches.append(agent_id)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ProtectedActionGate(
                "agent.bind",
                gate={
                    "kind": "agent_identity_selection_required",
                    "summary": "这个 Endpoint 对应多个 Goal Agent 身份，请先选择一个身份。",
                    "next_action": "在 Agent 设置中确认绑定身份后，再生成 Todo 预览。",
                    "endpoint_id": endpoint_id,
                    "candidate_agent_ids": matches,
                },
            )
        raise ProtectedActionGate(
            "agent.bind",
            gate={
                "kind": "agent_binding_required",
                "summary": "所选 Agent Endpoint 尚未绑定到这个 Goal。",
                "next_action": "先确认 Agent 绑定预览，再继续创建或改派 Todo。",
                "endpoint_id": endpoint_id,
                "goal_id": goal_id,
            },
        )

    def _goal_state_fingerprint(self, goal_id: str) -> str:
        goal = self._goal(goal_id)
        project = Path(str(goal.get("repo") or "")).expanduser().resolve()
        state_file = Path(str(goal.get("state_file") or ""))
        if not state_file.is_absolute():
            state_file = project / state_file
        try:
            state_digest = hashlib.sha256(state_file.read_bytes()).hexdigest()
        except OSError as exc:
            raise ValueError("the active Goal state is unavailable") from exc
        return _digest(
            {
                "registry": self._registry_fingerprint(),
                "goal_id": goal_id,
                "state": state_digest,
            }
        )

    @staticmethod
    def _allowed_parameters(
        parameters: Mapping[str, Any],
        *,
        allowed: set[str],
    ) -> dict[str, Any]:
        unknown = set(parameters) - allowed
        if unknown:
            raise ValueError(f"unknown typed action parameter: {sorted(unknown)[0]}")
        return dict(parameters)

    def _normalize(self, action_kind: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
        if action_kind == "todo.create":
            values = self._allowed_parameters(
                parameters,
                allowed={"goal_id", "text", "agent_id", "endpoint_id", "start_execution"},
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            result = {
                "goal_id": goal_id,
                "text": _text(values.get("text"), field="text", limit=400),
            }
            if values.get("endpoint_id"):
                endpoint_id = _opaque(values.get("endpoint_id"), field="endpoint_id")
                result["endpoint_id"] = endpoint_id
                result["agent_id"] = self._resolve_goal_agent(goal_id, endpoint_id)
            elif values.get("agent_id"):
                agent_id = _opaque(values.get("agent_id"), field="agent_id")
                if agent_id not in registered_agent_ids_for_goal(self._goal(goal_id)):
                    raise ProtectedActionGate(
                        "agent.bind",
                        gate={
                            "kind": "agent_binding_required",
                            "summary": "所选 Agent 身份尚未绑定到这个 Goal。",
                            "next_action": "先确认 Agent 绑定预览，再继续创建 Todo。",
                            "agent_id": agent_id,
                            "goal_id": goal_id,
                        },
                    )
                result["agent_id"] = agent_id
            if values.get("start_execution") is not None:
                if not isinstance(values["start_execution"], bool):
                    raise ValueError("start_execution must be true or false")
                result["start_execution"] = values["start_execution"]
            if result.get("start_execution") and not result.get("agent_id"):
                raise ValueError("start_execution requires an assigned Agent")
            return result
        if action_kind == "todo.update":
            values = self._allowed_parameters(
                parameters,
                allowed={
                    "goal_id",
                    "todo_id",
                    "text",
                    "status",
                    "note",
                    "agent_id",
                    "endpoint_id",
                    "operation",
                    "resume_when",
                    "successor_todo_ids",
                    "no_followup",
                },
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            result: dict[str, Any] = {
                "goal_id": goal_id,
                "todo_id": _opaque(values.get("todo_id"), field="todo_id"),
            }
            operation = str(values.get("operation") or "edit").strip().lower()
            if operation not in {"edit", "reassign", "block", "defer", "complete", "successor"}:
                raise ValueError(
                    "todo.update operation must be edit, reassign, block, defer, complete, or successor"
                )
            result["operation"] = operation
            if values.get("text"):
                result["text"] = _text(values["text"], field="text", limit=400)
            if values.get("status"):
                status = str(values["status"]).strip().lower()
                if status not in {"open", "blocked", "deferred"}:
                    raise ValueError("todo.update status must be open, blocked, or deferred")
                result["status"] = status
            if values.get("note"):
                result["note"] = _text(values["note"], field="note", limit=600)
            if values.get("endpoint_id"):
                endpoint_id = _opaque(values["endpoint_id"], field="endpoint_id")
                result["endpoint_id"] = endpoint_id
                result["agent_id"] = self._resolve_goal_agent(goal_id, endpoint_id)
            elif values.get("agent_id"):
                result["agent_id"] = _opaque(values["agent_id"], field="agent_id")
            if values.get("resume_when"):
                result["resume_when"] = require_supported_todo_resume_when(
                    _text(values["resume_when"], field="resume_when", limit=240)
                )
            if values.get("successor_todo_ids") is not None:
                if not isinstance(values["successor_todo_ids"], list):
                    raise ValueError("successor_todo_ids must be a list")
                result["successor_todo_ids"] = [
                    _opaque(item, field="successor_todo_ids")
                    for item in values["successor_todo_ids"][:20]
                ]
            if values.get("no_followup") is not None:
                if not isinstance(values["no_followup"], bool):
                    raise ValueError("no_followup must be true or false")
                result["no_followup"] = values["no_followup"]
            required_by_operation = {
                "reassign": "agent_id",
                "defer": "resume_when",
                "successor": "successor_todo_ids",
            }
            required = required_by_operation.get(operation)
            if required and not result.get(required):
                raise ValueError(f"todo.update {operation} requires {required}")
            if operation == "block" and not result.get("note"):
                raise ValueError("todo.update block requires note")
            if operation == "edit" and len(result) == 3:
                raise ValueError("todo.update requires text, status, or note")
            return result
        if action_kind == "run.correct":
            values = self._allowed_parameters(
                parameters,
                allowed={"goal_id", "session_id", "message", "client_turn_id"},
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            session_id = _opaque(values.get("session_id"), field="session_id")
            client_turn_id = values.get("client_turn_id")
            normalized = {
                "goal_id": goal_id,
                "session_id": session_id,
                "message": _text(values.get("message"), field="message", limit=4000),
            }
            if client_turn_id:
                normalized["client_turn_id"] = _opaque(client_turn_id, field="client_turn_id")
            return normalized
        if action_kind == "goal.create":
            values = self._allowed_parameters(
                parameters,
                allowed={
                    "goal_id",
                    "title",
                    "objective",
                    "completion_criteria",
                    "execution_boundary",
                    "agent_id",
                    "workspace_ref",
                    "permission",
                    "heartbeat",
                    "stop_condition",
                    "initial_todos",
                },
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            if any(str(goal.get("id") or "") == goal_id for goal in registry_goals(self._registry())):
                raise ValueError("goal_id already exists in the active LoopX registry")
            result: dict[str, Any] = {
                "goal_id": goal_id,
                "title": _text(values.get("title"), field="title", limit=200),
            }
            for field in (
                "objective",
                "completion_criteria",
                "execution_boundary",
                "permission",
                "stop_condition",
            ):
                if values.get(field):
                    result[field] = _text(values[field], field=field, limit=1000)
            for field in ("agent_id", "workspace_ref"):
                if values.get(field):
                    result[field] = _opaque(values[field], field=field)
            if result.get("agent_id"):
                self._agent_eligibility(str(result["agent_id"]))
            if values.get("heartbeat") is not None:
                if not isinstance(values["heartbeat"], Mapping):
                    raise ValueError("heartbeat must be an object")
                heartbeat = self._allowed_parameters(
                    values["heartbeat"], allowed={"enabled", "cadence", "timezone"}
                )
                enabled = heartbeat.get("enabled")
                if not isinstance(enabled, bool):
                    raise ValueError("heartbeat.enabled must be true or false")
                normalized_heartbeat: dict[str, Any] = {"enabled": enabled}
                if heartbeat.get("cadence"):
                    normalized_heartbeat["cadence"] = _normalize_cadence(
                        heartbeat["cadence"]
                    )
                if heartbeat.get("timezone"):
                    normalized_heartbeat["timezone"] = _text(
                        heartbeat["timezone"], field="heartbeat.timezone", limit=80
                    )
                result["heartbeat"] = normalized_heartbeat
            if values.get("initial_todos") is not None:
                if not isinstance(values["initial_todos"], list):
                    raise ValueError("initial_todos must be a list")
                result["initial_todos"] = [
                    _text(item, field="initial_todos", limit=400) for item in values["initial_todos"][:20]
                ]
            return result
        if action_kind == "goal.update":
            values = self._allowed_parameters(
                parameters,
                allowed={"goal_id", "title", "objective", "status", "write_scope"},
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            result = {"goal_id": goal_id}
            for field in ("title", "objective", "status"):
                if values.get(field):
                    result[field] = _text(values[field], field=field, limit=1000)
            if values.get("write_scope") is not None:
                if not isinstance(values["write_scope"], list):
                    raise ValueError("write_scope must be a list")
                result["write_scope"] = [
                    _text(item, field="write_scope", limit=160)
                    for item in values["write_scope"][:20]
                ]
            if len(result) == 1:
                raise ValueError("goal.update requires at least one change")
            return result
        if action_kind == "goal.lifecycle":
            return self._normalize_goal_lifecycle(parameters)
        if action_kind == "agent.bind":
            values = self._allowed_parameters(parameters, allowed={"goal_id", "agent_id"})
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            agent_id = _opaque(values.get("agent_id"), field="agent_id")
            self._agent_eligibility(agent_id)
            return {
                "goal_id": goal_id,
                "agent_id": agent_id,
            }
        if action_kind == "heartbeat.bind":
            values = self._allowed_parameters(
                parameters,
                allowed={
                    "goal_id",
                    "agent_id",
                    "cadence",
                    "timezone",
                    "stop_condition",
                    "notification_policy",
                    "operation",
                },
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            operation = str(values.get("operation") or "bind").strip().lower()
            if operation not in {"bind", "edit", "pause", "resume", "stop"}:
                raise ValueError("heartbeat operation must be bind, edit, pause, resume, or stop")
            agent_id = _opaque(values.get("agent_id"), field="agent_id")
            self._agent_eligibility(agent_id)
            result: dict[str, Any] = {
                "goal_id": goal_id,
                "agent_id": agent_id,
                "operation": operation,
            }
            if values.get("cadence"):
                result["cadence"] = _normalize_cadence(values["cadence"])
            if values.get("timezone"):
                result["timezone"] = _text(values["timezone"], field="timezone", limit=80)
            if values.get("stop_condition"):
                result["stop_condition"] = _text(
                    values["stop_condition"], field="stop_condition", limit=160
                ).lower()
            if values.get("notification_policy"):
                result["notification_policy"] = _opaque(
                    values["notification_policy"], field="notification_policy"
                )
            if operation == "bind" and not all(
                result.get(field) for field in ("cadence", "timezone", "stop_condition")
            ):
                raise ValueError("heartbeat bind requires cadence, timezone, and stop_condition")
            if operation == "edit" and len(result) == 3:
                raise ValueError("heartbeat edit requires a configuration change")
            return result
        if action_kind == "monitor.create":
            values = self._allowed_parameters(
                parameters,
                allowed={
                    "goal_id",
                    "agent_id",
                    "target",
                    "target_key",
                    "cadence",
                    "timezone",
                    "stop_condition",
                    "notification_rule",
                },
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            result = {
                "goal_id": goal_id,
                "agent_id": _opaque(values.get("agent_id"), field="agent_id"),
                "target": _text(values.get("target"), field="target", limit=400),
                "target_key": _opaque(values.get("target_key"), field="target_key"),
                "cadence": _normalize_cadence(values.get("cadence")),
                "timezone": _text(values.get("timezone"), field="timezone", limit=80),
            }
            stop_cond_raw = values.get("stop_condition")
            if stop_cond_raw:
                raw_text = _text(stop_cond_raw, field="stop_condition", limit=160)
                parsed_ts = parse_timestamp(raw_text)
                result["stop_condition"] = utc_isoformat(parsed_ts) if parsed_ts is not None else raw_text.lower()
            if values.get("notification_rule"):
                result["notification_rule"] = _text(
                    values["notification_rule"], field="notification_rule", limit=400
                )
            return result
        if action_kind == "monitor.update":
            values = self._allowed_parameters(
                parameters,
                allowed={
                    "goal_id",
                    "todo_id",
                    "agent_id",
                    "operation",
                    "target",
                    "target_key",
                    "cadence",
                    "stop_condition",
                    "session_id",
                    "endpoint_id",
                },
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            operation = str(values.get("operation") or "").strip().lower()
            if operation not in {"pause", "resume", "stop", "run_now", "edit"}:
                raise ValueError("monitor.update operation must be pause, resume, stop, run_now, or edit")
            result = {
                "goal_id": goal_id,
                "todo_id": _opaque(values.get("todo_id"), field="todo_id"),
                "agent_id": _opaque(values.get("agent_id"), field="agent_id"),
                "operation": operation,
            }
            if values.get("endpoint_id"):
                endpoint_id = _opaque(values["endpoint_id"], field="endpoint_id")
                result["endpoint_id"] = endpoint_id
                result["agent_id"] = self._resolve_goal_agent(goal_id, endpoint_id)
            if values.get("target"):
                result["target"] = _text(values["target"], field="target", limit=400)
            if values.get("target_key"):
                result["target_key"] = _opaque(values["target_key"], field="target_key")
            if values.get("cadence"):
                result["cadence"] = _normalize_cadence(values["cadence"])
            if values.get("stop_condition"):
                raw_stop = _text(values["stop_condition"], field="stop_condition", limit=160)
                parsed_ts = parse_timestamp(raw_stop)
                result["stop_condition"] = utc_isoformat(parsed_ts) if parsed_ts is not None else raw_stop.lower()
            if values.get("session_id"):
                result["session_id"] = _opaque(values["session_id"], field="session_id")
            if operation == "edit" and len(result) == 4:
                raise ValueError("monitor edit requires target, target_key, cadence, or stop_condition")
            return result
        if action_kind == "gate.resolve":
            values = self._allowed_parameters(
                parameters,
                allowed={"goal_id", "todo_id", "decision", "note", "agent_id"},
            )
            goal_id = _opaque(values.get("goal_id"), field="goal_id")
            self._goal(goal_id)
            decision = str(values.get("decision") or "").strip().lower()
            if decision not in {"approve", "reject", "cancel", "defer"}:
                raise ValueError("gate decision must be approve, reject, cancel, or defer")
            result = {
                "goal_id": goal_id,
                "todo_id": _opaque(values.get("todo_id"), field="todo_id"),
                "decision": decision,
            }
            if values.get("note"):
                result["note"] = _text(values["note"], field="note", limit=600)
            if values.get("agent_id"):
                result["agent_id"] = _opaque(values["agent_id"], field="agent_id")
            return result
        raise ValueError(f"unsupported action_kind: {action_kind}")

    def _session_fingerprint(self, session_id: str, goal_id: str) -> str:
        if self.chat_store is None:
            raise ValueError("Chat Session state is unavailable")
        session = self.chat_store.load_session(session_id)
        if session is None or session.get("status") == "closed":
            raise ValueError("chat session was not found")
        if str(session.get("goal_id") or "") != goal_id:
            raise ValueError("chat session does not belong to the selected Goal")
        return _digest(
            {
                "session_id": session_id,
                "goal_id": goal_id,
                "agent_id": session.get("agent_id"),
                "status": session.get("status"),
                "active_turn_id": session.get("active_turn_id"),
            }
        )

    def _project_for_goal_create(self, proposal: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
        parameters = proposal.get("normalized_parameters")
        context = proposal.get("context")
        if not isinstance(parameters, Mapping) or not isinstance(context, Mapping):
            raise ValueError("typed Chat action proposal is malformed")
        workspace_ref = str(parameters.get("workspace_ref") or "current")
        goals = registry_goals(self._registry())
        context_goal_id = str(context.get("goal_id") or "").strip()
        source_goal = next(
            (goal for goal in goals if str(goal.get("id") or "") == context_goal_id),
            None,
        )
        if source_goal is None and workspace_ref != "current":
            source_goal = next(
                (goal for goal in goals if str(goal.get("id") or "") == workspace_ref),
                None,
            )
        if source_goal is None and len(goals) == 1:
            source_goal = goals[0]
        if source_goal is None and workspace_ref == "current":
            workspace_candidates = [
                root for root in self.workspace_roots
                if root.is_dir() and (root / ".git").exists()
            ]
            if len(workspace_candidates) == 1:
                return workspace_candidates[0], {
                    "id": "",
                    "domain": "project-goal-control-plane",
                    "repo": str(workspace_candidates[0]),
                    "adapter": {"kind": "generic_project_goal_v0"},
                }
            token_map = {
                f"workspace-{hashlib.sha256(str(root).encode('utf-8')).hexdigest()[:12]}": root
                for root in workspace_candidates
            }
            if workspace_ref in token_map:
                selected = token_map[workspace_ref]
                return selected, {
                    "id": "",
                    "domain": "project-goal-control-plane",
                    "repo": str(selected),
                    "adapter": {"kind": "generic_project_goal_v0"},
                }
        elif source_goal is None and workspace_ref.startswith("workspace-"):
            workspace_candidates = [
                root for root in self.workspace_roots
                if root.is_dir() and (root / ".git").exists()
            ]
            selected = next(
                (
                    root
                    for root in workspace_candidates
                    if workspace_ref
                    == f"workspace-{hashlib.sha256(str(root).encode('utf-8')).hexdigest()[:12]}"
                ),
                None,
            )
            if selected is not None:
                return selected, {
                    "id": "",
                    "domain": "project-goal-control-plane",
                    "repo": str(selected),
                    "adapter": {"kind": "generic_project_goal_v0"},
                }
        if source_goal is None:
            candidates = [
                {
                    "workspace_ref": f"workspace-{hashlib.sha256(str(root).encode('utf-8')).hexdigest()[:12]}",
                    "label": f"Workspace {index}",
                }
                for index, root in enumerate(
                    (
                        root for root in self.workspace_roots
                        if root.is_dir() and (root / ".git").exists()
                    ),
                    start=1,
                )
            ]
            raise ProtectedActionGate(
                "goal.create",
                gate={
                    "kind": "workspace_selection_required",
                    "summary": "Select one server-configured workspace before creating this Goal.",
                    "next_action": "Start LoopX Chat with exactly one --scan-path workspace or regenerate from an existing Goal channel.",
                    "candidates": candidates,
                },
            )
        if workspace_ref not in {"current", str(source_goal.get("id") or "")}:
            raise ValueError("workspace_ref must be current or an existing Goal id")
        project = Path(str(source_goal.get("repo") or "")).expanduser().resolve()
        if not project.is_dir():
            raise ProtectedActionGate(
                "goal.create",
                gate={
                    "kind": "workspace_unavailable",
                    "summary": "The selected server-side Goal workspace is unavailable.",
                    "next_action": "Restore the registered workspace and regenerate this preview.",
                },
            )
        return project, source_goal

    def _apply_goal_create(
        self, proposal_id: str, proposal: dict[str, Any], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        current_fingerprint = self._registry_fingerprint()
        heartbeat = parameters.get("heartbeat") if isinstance(parameters.get("heartbeat"), dict) else {}
        goal_id = str(parameters["goal_id"])
        existing_goal = next(
            (
                goal
                for goal in registry_goals(self._registry())
                if str(goal.get("id") or "") == goal_id
            ),
            None,
        )
        if existing_goal is not None:
            project = Path(str(existing_goal.get("repo") or "")).expanduser().resolve()
            source_goal = existing_goal
        else:
            project, source_goal = self._project_for_goal_create(proposal)
        self._agent_eligibility(str(parameters.get("agent_id") or "codex"), project=project)
        self.store.save_checkpoint(
            proposal_id,
            step="workspace_validated",
            receipt={
                "outcome": "workspace_validated",
                "workspace_ref": str(parameters.get("workspace_ref") or "current"),
            },
        )
        recovering = existing_goal is not None
        if recovering:
            existing_project = Path(str(existing_goal.get("repo") or "")).expanduser().resolve()
            if existing_project != project:
                raise ProtectedActionGate(
                    "goal.create",
                    gate={
                        "kind": "goal_id_conflict",
                        "summary": "The Goal id now belongs to a different registered workspace.",
                        "next_action": "Choose another Goal id and regenerate the preview.",
                    },
                )
        elif current_fingerprint != proposal.get("expected_state_fingerprint"):
            stale = self.store.apply(
                proposal_id,
                current_state_fingerprint=current_fingerprint,
                receipt={},
            )
            return {"proposal": stale, "turn": None}
        registry = self._registry()
        runtime_root_value = registry.get("common_runtime_root")
        runtime_root = (
            Path(str(runtime_root_value)).expanduser().resolve()
            if runtime_root_value
            else None
        )
        objective = str(parameters.get("objective") or parameters["title"])
        result = (
            {"ok": True}
            if recovering
            else bootstrap_project(
                project=project,
                registry_path=self.registry_path,
                runtime_root=runtime_root,
                goal_id=goal_id,
                objective=objective,
                domain=str(source_goal.get("domain") or "project-goal-control-plane"),
                role="primary",
                parent_goal_id=str(source_goal.get("id") or "") or None,
                state_file=None,
                goal_doc=None,
                adapter_kind=str((source_goal.get("adapter") or {}).get("kind") or "generic_project_goal_v0"),
                adapter_status="connected",
                display_name=str(parameters.get("title") or "").strip() or None,
                onboarding_connection_validation="provider-prevalidated",
                next_probe=None,
                spawn_allowed=False,
                max_children=0,
                allowed_domains=[],
                write_scope=[],
                onboarding_scan_enabled=False,
                accept_onboarding_agent_todos=False,
                begin_autonomous_advance=False,
                codex_app_heartbeat="no",
                preserve_todos=True,
                force=False,
                dry_run=False,
                sync_global=False,
            )
        )
        if not result.get("ok"):
            raise ProtectedActionGate(
                "goal.create",
                gate={
                    "kind": "goal_bootstrap_blocked",
                    "summary": "Canonical Goal bootstrap did not complete.",
                    "next_action": "Repair the project registry write path and retry this preview.",
                },
            )
        self.store.save_checkpoint(
            proposal_id,
            step="goal_bootstrapped",
            receipt={"outcome": "goal_bootstrapped", "goal_id": goal_id},
        )
        agent_id = str(parameters.get("agent_id") or "").strip()
        if agent_id:
            configure_goal(
                registry_path=self.registry_path,
                goal_id=goal_id,
                registered_agents=[agent_id],
                execute=True,
            )
            self.store.save_checkpoint(
                proposal_id,
                step="agent_bound",
                receipt={"outcome": "agent_bound", "goal_id": goal_id, "agent_id": agent_id},
            )
        todo_ids: list[str] = []
        for todo_text in parameters.get("initial_todos") or []:
            todo = add_goal_todo(
                registry_path=self.registry_path,
                goal_id=goal_id,
                role="agent",
                text=str(todo_text),
                task_class="advancement_task",
                action_kind="advance",
                claimed_by=agent_id or None,
                agent_id=agent_id or None,
                dry_run=False,
            )
            if todo.get("todo_id"):
                todo_ids.append(str(todo["todo_id"]))
        self.store.save_checkpoint(
            proposal_id,
            step="todos_created",
            receipt={"outcome": "todos_created", "todo_ids": todo_ids},
        )
        projected = self._goal(goal_id)
        if agent_id and agent_id not in registered_agent_ids_for_goal(projected):
            raise ValueError("Goal projection did not retain the selected Agent binding")
        turn_result: dict[str, Any] | None = None
        session_id = ""
        first_turn_gate: dict[str, Any] | None = None
        try:
            from .status import collect_status

            status_payload = collect_status(
                registry_path=self.registry_path,
                runtime_root_override=str(runtime_root) if runtime_root else None,
                scan_roots=[project],
                limit=5,
                goal_id=goal_id,
                available_capabilities=(
                    self.runtime_controller.capabilities()
                    if self.runtime_controller is not None
                    else None
                ),
                include_public_boundary_scan=False,
            )
            guard = build_quota_should_run(
                status_payload,
                goal_id=goal_id,
                agent_id=agent_id or None,
                available_capabilities=(
                    self.runtime_controller.capabilities()
                    if self.runtime_controller is not None
                    else None
                ),
            )
        except Exception:
            guard = {"should_run": True, "state": "status_unavailable"}
        if guard.get("should_run") is not True:
            first_turn_gate = {
                "kind": "goal_quota_gate",
                "summary": str(
                    guard.get("reason")
                    or "The new Goal is not eligible for its first Agent Turn."
                )[:600],
                "next_action": str(
                    guard.get("recommended_action")
                    or "Resolve the projected Goal Gate and retry the first Turn."
                )[:600],
                "quota_state": str(guard.get("state") or "waiting"),
            }
        if agent_id and self.runtime_controller is not None and first_turn_gate is None:
            session, _resumed = self.runtime_controller.open_session(
                goal_id=goal_id,
                agent_id=agent_id,
                work_dir=project,
                objective=objective,
                mode="resume_latest",
                channel_id=f"goal.{goal_id}",
                agent_goal_id=goal_id,
            )
            session_id = _opaque(session.get("session_id"), field="session_id")
            first_turn, created = self.runtime_controller.submit_turn(
                session_id=session_id,
                client_turn_id=f"goal-start-{proposal_id}",
                message=(
                    f"开始推进 Goal {goal_id}。先核对目标边界和现有 Todo，"
                    f"首个 Todo：{'；'.join(str(item) for item in (parameters.get('initial_todos') or [])[:3]) or '按目标边界建立首个可验证进展'}。"
                    "然后直接推进并报告可验证结果；遇到权限边界时停止并提出明确 Gate。"
                ),
                work_dir=project,
                objective=objective,
            )
            turn_result = {
                "turn_id": _opaque(first_turn.get("turn_id"), field="turn_id"),
                "status": str(first_turn.get("status") or "queued"),
                "created": created,
            }
            self.store.save_checkpoint(
                proposal_id,
                step="first_turn_started",
                receipt={
                    "outcome": "first_turn_started",
                    "session_id": session_id,
                    "turn_id": turn_result["turn_id"],
                },
            )
        elif first_turn_gate is not None:
            self.store.save_checkpoint(
                proposal_id,
                step="first_turn_gated",
                receipt={"outcome": "first_turn_gated", "gate": first_turn_gate},
            )
        child_gate: dict[str, Any] | None = first_turn_gate
        if heartbeat.get("enabled") is True:
            heartbeat_parameters = {
                "goal_id": goal_id,
                "agent_id": agent_id or "codex",
                "operation": "bind",
                "cadence": str(heartbeat.get("cadence") or "1d"),
                "timezone": str(heartbeat.get("timezone") or "UTC"),
                "stop_condition": str(parameters.get("stop_condition") or "goal_complete"),
            }
            child_gate = self._heartbeat_gate(heartbeat_parameters).gate
            self.store.save_checkpoint(
                proposal_id,
                step="heartbeat_gate_ready",
                receipt={"outcome": "heartbeat_gate_ready", "gate": child_gate},
            )
        receipt = {
            "receipt_id": _digest({"proposal_id": proposal_id, "goal_id": goal_id})[:32],
            "outcome": "goal_created",
            "projection_verified": True,
            "resource_ids": {
                "goal_id": goal_id,
                **({"agent_id": agent_id} if agent_id else {}),
                **({"todo_ids": todo_ids} if todo_ids else {}),
                **({"session_id": session_id} if session_id else {}),
                **({"turn_id": turn_result["turn_id"]} if turn_result else {}),
            },
            **({"child_gate": child_gate} if child_gate else {}),
            "step_receipts": (
                (self.store.load(proposal_id) or {}).get("checkpoint") or {}
            ).get("steps", {}),
        }
        stored = self.store.apply(
            proposal_id,
            current_state_fingerprint=str(proposal["expected_state_fingerprint"]),
            receipt=receipt,
        )
        return {"proposal": stored, "turn": turn_result, "gate": child_gate}

    def _apply_agent_bind(
        self, proposal_id: str, proposal: dict[str, Any], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        current_fingerprint = self._registry_fingerprint()
        goal_id = str(parameters["goal_id"])
        agent_id = str(parameters["agent_id"])
        existing = registered_agent_ids_for_goal(self._goal(goal_id))
        if agent_id in existing and current_fingerprint != proposal.get("expected_state_fingerprint"):
            receipt = {
                "receipt_id": _digest({"proposal_id": proposal_id, "goal_id": goal_id, "agent_id": agent_id})[:32],
                "outcome": "agent_already_bound",
                "projection_verified": True,
                "resource_ids": {"goal_id": goal_id, "agent_id": agent_id},
            }
            stored = self.store.apply(
                proposal_id,
                current_state_fingerprint=str(proposal["expected_state_fingerprint"]),
                receipt=receipt,
            )
            return {"proposal": stored, "turn": None}
        if current_fingerprint != proposal.get("expected_state_fingerprint"):
            stale = self.store.apply(
                proposal_id, current_state_fingerprint=current_fingerprint, receipt={}
            )
            return {"proposal": stale, "turn": None}
        registered = sorted({*existing, agent_id})
        result = configure_goal(
            registry_path=self.registry_path,
            goal_id=goal_id,
            registered_agents=registered,
            execute=True,
        )
        projected = registered_agent_ids_for_goal(self._goal(goal_id))
        if agent_id not in projected:
            raise ValueError("Agent binding was not visible in the Goal projection")
        receipt = {
            "receipt_id": _digest({"proposal_id": proposal_id, "goal_id": goal_id, "agent_id": agent_id})[:32],
            "outcome": "agent_bound" if result.get("changed") else "agent_already_bound",
            "projection_verified": True,
            "resource_ids": {"goal_id": goal_id, "agent_id": agent_id},
        }
        stored = self.store.apply(
            proposal_id, current_state_fingerprint=current_fingerprint, receipt=receipt
        )
        return {"proposal": stored, "turn": None}

    def _heartbeat_gate(self, parameters: dict[str, Any]) -> ProtectedActionGate:
        goal_id = str(parameters["goal_id"])
        agent_id = str(parameters["agent_id"])
        registered = registered_agent_ids_for_goal(self._goal(goal_id))
        if agent_id not in registered:
            raise ValueError("heartbeat Agent must be registered for the Goal")
        packet = build_host_loop_activation_packet(
            agent_type="codex-app",
            goal_id=goal_id,
            agent_id=agent_id,
            registered_agents=registered,
        )
        operation = str(parameters.get("operation") or "bind")
        gate_receipt = _digest(
            {"goal_id": goal_id, "agent_id": agent_id, "operation": operation, "packet": packet}
        )[:32]
        return ProtectedActionGate(
            "heartbeat.bind",
            gate={
                "kind": "host_activation_required",
                "summary": "The Codex App host owns heartbeat automation creation.",
                "next_action": "Use automation_update with the canonical activation packet, then verify the installed automation before retrying.",
                "operation": operation,
                "gate_receipt": gate_receipt,
                "desired_configuration": {
                    key: parameters[key]
                    for key in (
                        "cadence",
                        "timezone",
                        "stop_condition",
                        "notification_policy",
                    )
                    if parameters.get(key) is not None
                },
                "activation_packet": packet,
            },
        )

    def _apply_monitor_create(
        self, proposal_id: str, proposal: dict[str, Any], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        current_fingerprint = self._registry_fingerprint()
        if current_fingerprint != proposal.get("expected_state_fingerprint"):
            stale = self.store.apply(
                proposal_id, current_state_fingerprint=current_fingerprint, receipt={}
            )
            return {"proposal": stale, "turn": None}
        goal_id = str(parameters["goal_id"])
        agent_id = str(parameters["agent_id"])
        if agent_id not in registered_agent_ids_for_goal(self._goal(goal_id)):
            raise ValueError("monitor Agent must be registered for the Goal")
        stop_condition = str(parameters.get("stop_condition") or "").strip()
        resume_when = None
        if (
            stop_condition
            and parse_timestamp(stop_condition) is None
            and stop_condition.lower() not in {"watch_only", "watch-only", "watch", "continuous", "never"}
        ):
            resume_when = stop_condition
        metadata = _monitor_metadata(parameters)
        if not (metadata.get("expires_at") or resume_when or metadata.get("watch_only")):
            metadata["watch_only"] = "true"
        result = add_goal_todo(
            registry_path=self.registry_path,
            goal_id=goal_id,
            role="agent",
            text=_monitor_text(parameters) or str(parameters["target"]),
            task_class="continuous_monitor",
            action_kind="observe",
            claimed_by=agent_id,
            agent_id=agent_id,
            resume_when=resume_when,
            monitor_metadata=metadata,
            dry_run=False,
        )
        todo_id = _opaque(result.get("todo_id"), field="todo_id")
        receipt = {
            "receipt_id": _digest({"proposal_id": proposal_id, "goal_id": goal_id, "todo_id": todo_id})[:32],
            "outcome": "monitor_already_exists" if result.get("already_exists") else "monitor_created",
            "projection_verified": True,
            "resource_ids": {"goal_id": goal_id, "todo_id": todo_id, "agent_id": agent_id},
        }
        stored = self.store.apply(
            proposal_id, current_state_fingerprint=current_fingerprint, receipt=receipt
        )
        return {"proposal": stored, "turn": None}

    def preview(self, request: Mapping[str, Any]) -> dict[str, Any]:
        unknown = set(request) - {
            "action_kind",
            "summary",
            "normalized_parameters",
            "context",
            "idempotency_key",
        }
        if unknown:
            raise ValueError(f"unknown typed action field: {sorted(unknown)[0]}")
        action_kind = str(request.get("action_kind") or "").strip()
        if action_kind not in SUPPORTED_ACTION_KINDS:
            raise ValueError(f"unsupported action_kind: {action_kind or '<empty>'}")
        parameters = request.get("normalized_parameters")
        context = request.get("context")
        if not isinstance(parameters, Mapping) or not isinstance(context, Mapping):
            raise ValueError("normalized_parameters and context must be objects")
        normalized = self._normalize(action_kind, parameters)
        if action_kind == "goal.create":
            project, _source_goal = self._project_for_goal_create(
                {
                    "normalized_parameters": normalized,
                    "context": dict(context),
                }
            )
            agent_id = str(normalized.get("agent_id") or "codex")
            eligibility = self._agent_eligibility(agent_id, project=project)
        else:
            eligibility = None
        if action_kind == "todo.create":
            canonical_preview = build_todo_review_preview(
                registry_path=self.registry_path,
                goal_id=normalized["goal_id"],
                text=normalized["text"],
            )
            fingerprint = str(canonical_preview["preview_id"])
            evidence = ["Canonical LoopX Todo dry-run validated the proposal."]
            permission = "durable_write"
        elif action_kind == "run.correct":
            fingerprint = self._session_fingerprint(
                normalized["session_id"], normalized["goal_id"]
            )
            evidence = ["The recoverable Goal and Agent Chat Session is available."]
            permission = "scoped_correction"
        elif action_kind in {"todo.update", "monitor.update"}:
            if action_kind == "todo.update":
                canonical_preview = self._run_todo_update(normalized, dry_run=True)
                if canonical_preview.get("ok") is not True:
                    raise ValueError(
                        str(canonical_preview.get("error") or "Todo transition failed canonical dry-run validation")
                    )
            goal_fingerprint = self._goal_state_fingerprint(normalized["goal_id"])
            if action_kind == "monitor.update" and normalized.get("operation") == "run_now":
                session_id = normalized.get("session_id")
                fingerprint = (
                    _digest(
                        {
                            "goal": goal_fingerprint,
                            "session": self._session_fingerprint(
                                session_id, normalized["goal_id"]
                            ),
                        }
                    )
                    if session_id
                    else goal_fingerprint
                )
            else:
                fingerprint = goal_fingerprint
            evidence = [
                "Canonical LoopX Todo dry-run validated the requested transition."
                if action_kind == "todo.update"
                else "Canonical LoopX Todo state validated the requested transition."
            ]
            permission = "durable_write"
        else:
            fingerprint = self._registry_fingerprint()
            evidence = ["Canonical LoopX contracts validated the bounded request shape."]
            permission = "durable_write"
        if eligibility is not None:
            evidence.extend(
                [
                    "The selected Agent endpoint is healthy and tool-capable.",
                    "The selected Agent trust scope and workspace route are compatible.",
                ]
            )
        proposal = self.store.create_preview(
            action_kind=action_kind,
            summary=_text(request.get("summary"), field="summary", limit=600),
            normalized_parameters=normalized,
            context=dict(context),
            expected_state_fingerprint=fingerprint,
            permission_classification=permission,
            validation_evidence=evidence,
            available_transitions=["apply", "cancel"],
            idempotency_key=_opaque(request.get("idempotency_key"), field="idempotency_key"),
        )
        return proposal

    def load(self, proposal_id: str) -> dict[str, Any] | None:
        return self.store.load(proposal_id)

    def cancel(self, proposal_id: str) -> dict[str, Any]:
        return self.store.cancel(proposal_id)

    def reject(self, proposal_id: str) -> dict[str, Any]:
        return self.store.mark_rejected(proposal_id)

    def defer(self, proposal_id: str) -> dict[str, Any]:
        return self.store.mark_deferred(proposal_id)

    def regenerate(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.store.load(proposal_id)
        if proposal is None:
            raise KeyError("typed Chat action proposal was not found")
        if proposal.get("status") not in {"stale", "failed", "gated", "rejected"}:
            raise ActionConflictError(
                f"proposal in {proposal.get('status')} state cannot be regenerated"
            )
        regenerated = self.preview(
            {
                "action_kind": proposal.get("action_kind"),
                "summary": proposal.get("summary"),
                "normalized_parameters": proposal.get("normalized_parameters"),
                "context": proposal.get("context"),
                "idempotency_key": f"regenerate-{proposal_id}-{_digest(proposal)[:16]}",
            }
        )
        return self.store.link_regeneration(
            str(regenerated["proposal_id"]), regenerated_from=proposal_id
        )

    def apply(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.store.load(proposal_id)
        if proposal is None:
            raise KeyError("typed Chat action proposal was not found")
        if proposal.get("status") == "applied":
            return {"proposal": proposal, "turn": self._turn_from_receipt(proposal.get("receipt"))}
        proposal = self.store.start_apply(proposal_id)
        action_kind = str(proposal.get("action_kind") or "")
        parameters = proposal.get("normalized_parameters")
        if not isinstance(parameters, dict):
            raise ValueError("typed Chat action proposal is malformed")
        if action_kind == "goal.create":
            return self._apply_goal_create(proposal_id, proposal, parameters)
        if action_kind == "goal.lifecycle":
            return self._apply_goal_lifecycle(proposal_id, proposal, parameters)
        if action_kind == "agent.bind":
            return self._apply_agent_bind(proposal_id, proposal, parameters)
        if action_kind == "heartbeat.bind":
            raise self._heartbeat_gate(parameters)
        if action_kind == "monitor.create":
            return self._apply_monitor_create(proposal_id, proposal, parameters)
        if action_kind == "todo.update":
            return self._apply_todo_update(proposal_id, proposal, parameters)
        if action_kind == "monitor.update":
            return self._apply_monitor_update(proposal_id, proposal, parameters)
        if action_kind in {"goal.update", "gate.resolve"}:
            raise ProtectedActionGate(
                action_kind,
                gate={
                    "kind": "canonical_authority_required",
                    "summary": f"{action_kind} requires a narrower canonical authority contract.",
                    "next_action": "Keep this preview and resolve the action through the Goal configuration or Gate lifecycle surface.",
                },
            )
        if action_kind == "todo.create":
            checkpoint = proposal.get("checkpoint")
            steps = checkpoint.get("steps") if isinstance(checkpoint, dict) else {}
            steps = steps if isinstance(steps, dict) else {}
            todo_step = steps.get("todo_created")
            if isinstance(todo_step, dict) and todo_step.get("todo_id"):
                todo_id = _opaque(todo_step.get("todo_id"), field="todo_id")
                canonical_receipt = todo_step.get("canonical_receipt")
                if not isinstance(canonical_receipt, dict):
                    raise ValueError("Todo creation checkpoint is malformed")
                current_fingerprint = str(proposal.get("expected_state_fingerprint") or "")
            else:
                current = build_todo_review_preview(
                    registry_path=self.registry_path,
                    goal_id=str(parameters["goal_id"]),
                    text=str(parameters["text"]),
                )
                current_fingerprint = str(current["preview_id"])
                if current_fingerprint != proposal.get("expected_state_fingerprint"):
                    stale = self.store.apply(
                        proposal_id,
                        current_state_fingerprint=current_fingerprint,
                        receipt={},
                    )
                    return {"proposal": stale, "turn": None}
                applied = apply_todo_review_preview(
                    registry_path=self.registry_path,
                    goal_id=str(parameters["goal_id"]),
                    text=str(parameters["text"]),
                    preview_id=current_fingerprint,
                )
                canonical_receipt = applied["receipt"]
                todo_id = _opaque(canonical_receipt["todo_id"], field="todo_id")
                self.store.save_checkpoint(
                    proposal_id,
                    step="todo_created",
                    receipt={
                        "todo_id": todo_id,
                        "canonical_receipt": canonical_receipt,
                    },
                )
            agent_id = parameters.get("agent_id")
            if agent_id and not isinstance(steps.get("todo_assigned"), dict):
                update_goal_todo(
                    registry_path=self.registry_path,
                    goal_id=str(parameters["goal_id"]),
                    todo_id=todo_id,
                    claimed_by=str(agent_id),
                    agent_id=str(agent_id),
                    authority_reason="owner-confirmed typed Chat action",
                    dry_run=False,
                )
                self.store.save_checkpoint(
                    proposal_id,
                    step="todo_assigned",
                    receipt={"todo_id": todo_id, "agent_id": str(agent_id)},
                )
            receipt = {
                "receipt_id": str(canonical_receipt["receipt_id"]),
                "outcome": str(canonical_receipt["outcome"]),
                "projection_verified": True,
                "resource_ids": {
                    "goal_id": str(canonical_receipt["goal_id"]),
                    "todo_id": todo_id,
                    **({"agent_id": str(agent_id)} if agent_id else {}),
                },
                "canonical_receipt": canonical_receipt,
            }
            turn_result = None
            if parameters.get("start_execution"):
                if self.runtime_controller is None:
                    raise ValueError("Chat Runtime Controller is unavailable")
                execution_agent_id = str(
                    parameters.get("endpoint_id") or parameters["agent_id"]
                )
                execution_step = steps.get("execution_started")
                if isinstance(execution_step, dict) and execution_step.get("session_id"):
                    session_id = _opaque(execution_step.get("session_id"), field="session_id")
                    turn_id = _opaque(execution_step.get("turn_id"), field="turn_id")
                    created = False
                else:
                    goal = self._goal(str(parameters["goal_id"]))
                    project = Path(str(goal.get("repo") or ".")).expanduser().resolve()
                    if not project.is_dir():
                        raise ValueError("the Goal project root is unavailable")
                    self._agent_eligibility(execution_agent_id, project=project)
                    session, _resumed = self.runtime_controller.open_session(
                        goal_id=str(parameters["goal_id"]),
                        agent_id=execution_agent_id,
                        work_dir=project,
                        objective=str(parameters["text"]),
                        mode="resume_latest",
                        channel_id=f"task.{todo_id}",
                        agent_goal_id=str(parameters["goal_id"]),
                    )
                    session_id = _opaque(session.get("session_id"), field="session_id")
                    turn, created = self.runtime_controller.submit_turn(
                        session_id=session_id,
                        client_turn_id=f"task-start-{proposal_id}",
                        message=str(parameters["text"]),
                        work_dir=project,
                        objective=str(parameters["text"]),
                    )
                    turn_id = _opaque(turn.get("turn_id"), field="turn_id")
                    self.store.save_checkpoint(
                        proposal_id,
                        step="execution_started",
                        receipt={"session_id": session_id, "turn_id": turn_id},
                    )
                receipt["resource_ids"].update(
                    {"session_id": session_id, "turn_id": turn_id}
                )
                receipt["outcome"] = "task_execution_started"
                turn_result = {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "status": "queued",
                    "created": created,
                }
            stored = self.store.apply(
                proposal_id,
                current_state_fingerprint=current_fingerprint,
                receipt=receipt,
            )
            return {"proposal": stored, "turn": turn_result}
        if action_kind == "run.correct":
            if self.runtime_controller is None or self.chat_store is None:
                raise ValueError("Chat Runtime Controller is unavailable")
            current_fingerprint = self._session_fingerprint(
                str(parameters["session_id"]), str(parameters["goal_id"])
            )
            if current_fingerprint != proposal.get("expected_state_fingerprint"):
                stale = self.store.apply(
                    proposal_id,
                    current_state_fingerprint=current_fingerprint,
                    receipt={},
                )
                return {"proposal": stale, "turn": None}
            goal = self._goal(str(parameters["goal_id"]))
            project = Path(str(goal.get("repo") or ".")).expanduser().resolve()
            if not project.is_dir():
                raise ValueError("the Goal project root is unavailable")
            client_turn_id = str(parameters.get("client_turn_id") or f"action-{proposal_id}")
            turn, created = self.runtime_controller.submit_turn(
                session_id=str(parameters["session_id"]),
                client_turn_id=client_turn_id,
                message=str(parameters["message"]),
                work_dir=project,
                objective=str(goal.get("domain") or parameters["goal_id"]),
            )
            turn_id = _opaque(turn.get("turn_id"), field="turn_id")
            receipt = {
                "receipt_id": _digest(
                    {"proposal_id": proposal_id, "session_id": parameters["session_id"], "turn_id": turn_id}
                )[:32],
                "outcome": "turn_created" if created else "turn_already_exists",
                "projection_verified": True,
                "resource_ids": {
                    "goal_id": str(parameters["goal_id"]),
                    "session_id": str(parameters["session_id"]),
                    "turn_id": turn_id,
                },
            }
            stored = self.store.apply(
                proposal_id,
                current_state_fingerprint=current_fingerprint,
                receipt=receipt,
            )
            return {
                "proposal": stored,
                "turn": {"turn_id": turn_id, "status": str(turn.get("status") or "queued"), "created": created},
            }
        raise ValueError(f"unsupported action_kind: {action_kind}")

    @staticmethod
    def _turn_from_receipt(receipt: Any) -> dict[str, Any] | None:
        if not isinstance(receipt, dict) or not isinstance(receipt.get("resource_ids"), dict):
            return None
        resource_ids = receipt["resource_ids"]
        if not resource_ids.get("turn_id"):
            return None
        return {
            "session_id": str(resource_ids["session_id"]) if resource_ids.get("session_id") else None,
            "turn_id": str(resource_ids["turn_id"]),
            "status": "accepted",
            "created": receipt.get("outcome") in {"turn_created", "task_execution_started"},
        }
