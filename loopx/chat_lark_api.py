from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .control_plane.runtime.runtime_projection_route import (
    resolve_goal_source_runtime_route,
)
from .extensions.lark.goal_channel import (
    default_goal_channel_binding_path,
    default_goal_channel_target_path,
    read_goal_channel_binding,
    read_goal_channel_targets,
)
from .extensions.lark.app_setup import LarkAppSetupManager
from .extensions.lark.cli_resolution import LarkCliResolution, LarkCliUnavailableError
from .extensions.lark.goal_topic_connections import (
    LarkGroupChatLookupError,
    connect_lark_goal_topic,
    disconnect_lark_goal_topic,
    list_lark_apps,
    list_lark_connections,
    list_lark_group_chats,
)
from .extensions.lark.goal_topic_batch import connect_lark_goal_topics
from .extensions.lark.presentation.kanban import (
    CommandRunner,
    default_subprocess_runner,
)
from .history import load_registry
from .paths import resolve_runtime_root
from .registry import registry_goals
from .repository_identity import normalize_repository_identity


def _compact_text(value: Any, *, limit: int = 600) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def _parse_lark_agent_bindings(
    body: Mapping[str, Any],
) -> dict[str, str] | None:
    raw_bindings = body.get("agent_bindings")
    if raw_bindings is None:
        return None
    if body.get("agent_id") or body.get("app_ref"):
        raise ValueError("agent_bindings cannot be combined with agent_id or app_ref")
    if not isinstance(raw_bindings, list):
        raise ValueError("agent_bindings must be a list")
    bindings: dict[str, str] = {}
    for item in raw_bindings:
        if not isinstance(item, Mapping) or set(item) != {"agent_id", "app_ref"}:
            raise ValueError("each agent binding must contain agent_id and app_ref")
        agent_id = _compact_text(item.get("agent_id"), limit=160)
        app_ref = _compact_text(item.get("app_ref"), limit=100)
        if not agent_id or not app_ref:
            raise ValueError("each agent binding requires agent_id and app_ref")
        if agent_id in bindings:
            raise ValueError("each Agent may appear only once in a batch")
        bindings[agent_id] = app_ref
    return bindings


def _connection_packet_has_committed_binding(packet: Mapping[str, Any]) -> bool:
    """Return whether an executed connection packet committed any binding."""

    if packet.get("ok") is True:
        return True
    details = packet.get("details")
    if not isinstance(details, Mapping):
        return False
    completed = details.get("completed_agent_ids")
    return isinstance(completed, list) and bool(completed)


def _default_git_runner(args: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"returncode": 1, "stdout": ""}
    return {"returncode": completed.returncode, "stdout": completed.stdout}


def build_goal_repository_contexts(
    *,
    registry: dict[str, Any],
    git_runner: Any = _default_git_runner,
) -> list[dict[str, Any]]:
    """Return local-API Goal repository labels without checkout paths."""

    rows: list[dict[str, Any]] = []
    for goal in registry_goals(registry):
        goal_id = str(goal.get("id") or "").strip()
        repo_text = str(goal.get("repo") or "").strip()
        if not goal_id or not repo_text:
            continue
        project = Path(repo_text).expanduser().resolve()
        remote_result = git_runner(
            ["git", "-C", str(project), "config", "--get", "remote.origin.url"]
        )
        remote = str(remote_result.get("stdout") or "").strip()
        try:
            identity = normalize_repository_identity(remote)
        except ValueError:
            identity = f"loopx:{goal_id}"
        branch_result = git_runner(
            ["git", "-C", str(project), "branch", "--show-current"]
        )
        branch = _compact_text(branch_result.get("stdout"), limit=160)
        label = (
            identity.split("/", 1)[1]
            if identity.startswith("git:") and "/" in identity
            else goal_id
        )
        rows.append(
            {
                "goal_id": goal_id,
                "repository": {
                    "branch": branch,
                    "identity": identity,
                    "label": label,
                    "read_only": True,
                },
            }
        )
    return rows


def build_lark_goal_topic_runtime_snapshot(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
) -> dict[str, Any]:
    """Load local-private App targets, per-Goal bindings, and execution context."""

    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(
        registry,
        runtime_root_override,
        registry_path=registry_path,
    )
    target_payload = read_goal_channel_targets(
        default_goal_channel_target_path(runtime_root)
    )
    binding_payloads: dict[str, dict[str, Any]] = {}
    goal_contexts: dict[str, dict[str, str]] = {}
    for goal in registry_goals(registry):
        goal_id = str(goal.get("id") or "").strip()
        repo = str(goal.get("repo") or "").strip()
        if not goal_id or not repo:
            continue
        goal_contexts[goal_id] = {
            "work_dir": str(Path(repo).expanduser().resolve()),
            "objective": _compact_text(goal.get("objective") or goal_id, limit=600),
        }
        try:
            route = resolve_goal_source_runtime_route(
                registry_path=registry_path,
                goal_id=goal_id,
                registry=registry,
            )
            source_registry_path = Path(str(route["source_registry"]))
            if source_registry_path.parent.name != ".loopx":
                continue
            binding_payloads[goal_id] = read_goal_channel_binding(
                default_goal_channel_binding_path(source_registry_path)
            )
        except (KeyError, OSError, ValueError):
            continue
    return {
        "target_payload": target_payload,
        "binding_payloads": binding_payloads,
        "goal_contexts": goal_contexts,
    }


class LarkChatRequestMixin:
    """Loopback HTTP handlers for Goal repository and Lark topic connections."""

    server: Any
    path: str

    def _goal_channel_context(self, goal_id: str) -> tuple[dict[str, Any], Path]:
        registry, _goal = self._registry_and_goal(goal_id)
        route = resolve_goal_source_runtime_route(
            registry_path=self.server.registry_path,
            goal_id=goal_id,
            registry=registry,
        )
        source_registry_path = Path(str(route["source_registry"]))
        source_registry = (
            registry
            if source_registry_path.expanduser().resolve()
            == self.server.registry_path.expanduser().resolve()
            else load_registry(source_registry_path)
        )
        return source_registry, default_goal_channel_binding_path(source_registry_path)

    def _goal_channel_target_path(self) -> Path:
        registry = load_registry(self.server.registry_path)
        runtime_root = resolve_runtime_root(
            registry,
            self.server.runtime_root_override,
            registry_path=self.server.registry_path,
        )
        return default_goal_channel_target_path(runtime_root)

    def _lark_runner(self) -> CommandRunner:
        return getattr(self.server, "lark_runner", default_subprocess_runner)

    def _lark_resolution(self) -> LarkCliResolution:
        resolution = getattr(self.server, "lark_cli_resolution", None)
        if isinstance(resolution, LarkCliResolution):
            return resolution
        return LarkCliResolution(
            command="lark-cli",
            available=True,
            source="path",
            version=None,
            error_code=None,
        )

    def _lark_cli_bin(self) -> str:
        resolution = self._lark_resolution()
        if not resolution.available or not resolution.command:
            raise LarkCliUnavailableError(
                resolution.error_code or "lark_cli_not_installed"
            )
        return resolution.command

    def _require_lark_cli(self) -> str | None:
        try:
            return self._lark_cli_bin()
        except LarkCliUnavailableError as exc:
            self._send_error(
                str(exc),
                status=503,
                error_code=exc.error_code,
            )
            return None

    def _lark_setup_manager(self) -> LarkAppSetupManager:
        return self.server.lark_app_setup_manager

    def _refresh_lark_goal_topic_runtime(self) -> None:
        runtime = getattr(self.server, "lark_goal_topic_runtime", None)
        if runtime is not None:
            runtime.refresh()

    def _lark_binding_paths(self, registry: dict[str, Any]) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for goal in registry_goals(registry):
            goal_id = str(goal.get("id") or "").strip()
            if not goal_id:
                continue
            try:
                route = resolve_goal_source_runtime_route(
                    registry_path=self.server.registry_path,
                    goal_id=goal_id,
                    registry=registry,
                )
                source_registry_path = Path(str(route["source_registry"]))
                if source_registry_path.parent.name == ".loopx":
                    paths[goal_id] = default_goal_channel_binding_path(
                        source_registry_path
                    )
            except (OSError, ValueError):
                continue
        return paths

    def _goal_contexts(self) -> None:
        registry = load_registry(self.server.registry_path)
        self._send_json(
            {
                "ok": True,
                "schema_version": "loopx_chat_goal_contexts_v0",
                "goals": build_goal_repository_contexts(registry=registry),
            }
        )

    def _lark_apps(self) -> None:
        cli_bin = self._require_lark_cli()
        if cli_bin is None:
            return
        self._send_json(
            {
                "ok": True,
                "schema_version": "loopx_lark_apps_v0",
                "apps": list_lark_apps(
                    runner=self._lark_runner(),
                    cli_bin=cli_bin,
                ),
            }
        )

    def _lark_setup_start(self) -> None:
        try:
            body = self._read_json()
            if set(body) - {"app_ref", "brand"}:
                raise ValueError("unknown Lark App setup field")
            snapshot = self._lark_setup_manager().start(
                app_ref=_compact_text(body.get("app_ref"), limit=100),
                brand=_compact_text(body.get("brand"), limit=20) or "feishu",
            )
        except LarkCliUnavailableError as exc:
            self._send_error(str(exc), status=503, error_code=exc.error_code)
            return
        except ValueError as exc:
            self._send_error(str(exc), status=400, error_code="invalid_lark_app_setup")
            return
        self._send_json({"ok": True, **snapshot}, status=202)

    def _lark_setup_snapshot(self, setup_id: str) -> None:
        try:
            snapshot = self._lark_setup_manager().snapshot(setup_id)
        except KeyError:
            self._send_error(
                "Lark App setup was not found",
                status=404,
                error_code="lark_app_setup_not_found",
            )
            return
        self._send_json({"ok": True, **snapshot})

    def _lark_setup_cancel(self, setup_id: str) -> None:
        try:
            snapshot = self._lark_setup_manager().cancel(setup_id)
        except KeyError:
            self._send_error(
                "Lark App setup was not found",
                status=404,
                error_code="lark_app_setup_not_found",
            )
            return
        self._send_json({"ok": True, **snapshot})

    def _lark_chats(self) -> None:
        cli_bin = self._require_lark_cli()
        if cli_bin is None:
            return
        query = parse_qs(urlparse(self.path).query)
        app_ref = _compact_text(query.get("app_ref", [""])[0], limit=100)
        keyword = _compact_text(query.get("query", [""])[0], limit=120)
        if not app_ref:
            self._send_error(
                "app_ref is required", status=400, error_code="lark_app_required"
            )
            return
        try:
            chats = list_lark_group_chats(
                app_ref=app_ref,
                query=keyword or None,
                runner=self._lark_runner(),
                cli_bin=cli_bin,
            )
        except ValueError as exc:
            self._send_error(str(exc), status=400, error_code="invalid_lark_app")
            return
        except LarkGroupChatLookupError as exc:
            self._send_error(
                str(exc),
                status=502,
                error_code=exc.error_code,
            )
            return
        self._send_json(
            {
                "ok": True,
                "schema_version": "loopx_lark_group_chats_v0",
                "chats": chats,
            }
        )

    def _lark_connections(self) -> None:
        cli_bin = self._require_lark_cli()
        if cli_bin is None:
            return
        registry = load_registry(self.server.registry_path)
        self._send_json(
            {
                "ok": True,
                "schema_version": "loopx_lark_goal_topic_connections_v0",
                "connections": list_lark_connections(
                    registry=registry,
                    target_path=self._goal_channel_target_path(),
                    binding_paths=self._lark_binding_paths(registry),
                    runner=self._lark_runner(),
                    cli_bin=cli_bin,
                    runtime_health=(
                        self.server.lark_goal_topic_runtime.health_snapshot()
                        if getattr(self.server, "lark_goal_topic_runtime", None)
                        is not None
                        else None
                    ),
                ),
            }
        )

    def _lark_connect(self) -> None:
        cli_bin = self._require_lark_cli()
        if cli_bin is None:
            return
        try:
            body = self._read_json()
            allowed = {
                "agent_id",
                "agent_bindings",
                "app_ref",
                "capture_scope",
                "chat_id",
                "chat_name",
                "execute",
                "goal_id",
                "incoming_mode",
                "ingress_mode",
                "reply_mode",
            }
            if set(body) - allowed:
                raise ValueError("unknown Lark connection field")
            goal_id = _compact_text(body.get("goal_id"), limit=160)
            app_ref = _compact_text(body.get("app_ref"), limit=100)
            chat_id = _compact_text(body.get("chat_id"), limit=160)
            chat_name = _compact_text(body.get("chat_name"), limit=120)
            incoming_mode = (
                _compact_text(body.get("incoming_mode"), limit=40) or "mentions"
            )
            agent_id = _compact_text(body.get("agent_id"), limit=160) or None
            capture_scope = _compact_text(body.get("capture_scope"), limit=40) or None
            ingress_mode = (
                _compact_text(body.get("ingress_mode"), limit=40) or "async_inbox"
            )
            reply_mode = (
                _compact_text(body.get("reply_mode"), limit=40) or "topic_reply"
            )
            app_refs_by_agent = _parse_lark_agent_bindings(body)
            if (
                not goal_id
                or not chat_id
                or not chat_name
                or (app_refs_by_agent is None and not app_ref)
                or (app_refs_by_agent is not None and not app_refs_by_agent)
            ):
                raise ValueError(
                    "goal_id, one or more App bindings, chat_id, and chat_name are required"
                )
            registry, binding_path = self._goal_channel_context(goal_id)
            session_id: str | None = None
            session_ids_by_agent: dict[str, str] = {}
            if ingress_mode in {"live_steering", "session_queue"}:
                session_agent_ids = (
                    list(app_refs_by_agent) if app_refs_by_agent is not None else [agent_id]
                )
                if not all(session_agent_ids):
                    raise ValueError(f"{ingress_mode} requires a registered agent_id")
                for session_agent_id in session_agent_ids:
                    session = self.server.chat_store.latest_session(
                        goal_id=goal_id,
                        agent_id=session_agent_id,
                        channel_id=f"goal.{goal_id}",
                    )
                    if session is None:
                        raise ValueError(
                            f"{ingress_mode} requires an existing working session for this Goal and Agent"
                        )
                    session_ids_by_agent[str(session_agent_id)] = str(
                        session["session_id"]
                    )
                if agent_id:
                    session_id = session_ids_by_agent[agent_id]
            common = {
                "registry": registry,
                "goal_id": goal_id,
                "target_path": self._goal_channel_target_path(),
                "binding_path": binding_path,
                "chat_id": chat_id,
                "chat_name": chat_name,
                "incoming_mode": incoming_mode,
                "capture_scope": capture_scope,
                "ingress_mode": ingress_mode,
                "reply_mode": reply_mode,
                "registry_path": binding_path.parent / "registry.json",
                "execute": body.get("execute") is True,
                "runner": self._lark_runner(),
                "cli_bin": cli_bin,
            }
            if app_refs_by_agent is not None:
                packet = connect_lark_goal_topics(
                    **common,
                    app_refs_by_agent=app_refs_by_agent,
                    session_ids_by_agent=session_ids_by_agent,
                )
            else:
                packet = connect_lark_goal_topic(
                    **common,
                    app_ref=app_ref,
                    agent_id=agent_id,
                    session_id=session_id,
                )
        except ValueError as exc:
            self._send_error(str(exc), status=400, error_code="invalid_lark_connection")
            return
        except Exception:
            self._send_error(
                "the Lark connection operation failed before a verified provider receipt",
                status=400,
                error_code="provider_api_failed",
            )
            return
        if not packet.get("ok"):
            packet["error"] = _compact_text(
                packet.get("public_summary")
                or packet.get("blocker")
                or "Lark connection failed"
            )
        if (
            body.get("execute") is True
            and _connection_packet_has_committed_binding(packet)
        ):
            self._refresh_lark_goal_topic_runtime()
        self._send_json(packet, status=200 if packet.get("ok") else 400)

    def _lark_disconnect(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        goal_id = _compact_text(query.get("goal_id", [""])[0], limit=160)
        connection_id = _compact_text(query.get("connection_id", [""])[0], limit=160)
        if not goal_id or not connection_id:
            self._send_error(
                "goal_id and connection_id are required",
                status=400,
                error_code="connection_required",
            )
            return
        try:
            _registry, binding_path = self._goal_channel_context(goal_id)
            packet = disconnect_lark_goal_topic(
                binding_path=binding_path,
                goal_id=goal_id,
                connection_id=connection_id,
                registry_path=binding_path.parent / "registry.json",
            )
        except (OSError, ValueError) as exc:
            self._send_error(str(exc), status=400, error_code="invalid_lark_connection")
            return
        self._refresh_lark_goal_topic_runtime()
        self._send_json(packet)
