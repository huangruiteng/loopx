from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from ..runtime.public_safety import public_safe_compact_text
from ..todos.contract import normalize_todo_claimed_by, normalize_todo_id


AGENT_MANAGEMENT_PROJECTION_SCHEMA_VERSION = "agent_management_projection_v0"
TODO_ROW_SCHEMA_VERSION = "todo_row_v0"
AGENT_MANAGEMENT_MODE = "read_only"
MAX_AGENT_ROWS = 24
MAX_AGENT_TODOS = 8
MAX_REFS = 1
MAX_WORKSPACE_SCOPES = 4
STALE_CLAIM_THRESHOLD_HOURS = 36

_PRIORITY_RANK = {
    "P0": 0,
    "P0-LOCAL": 0,
    "P0-USER": 0,
    "P0-DECISION": 0,
    "P1": 1,
    "P2": 2,
}
def _compact(value: Any, *, limit: int = 220) -> str | None:
    return public_safe_compact_text(value, limit=limit)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _string_list(value: Any, *, limit: int = MAX_WORKSPACE_SCOPES) -> list[str]:
    items = value if isinstance(value, list) else [value] if value not in (None, "") else []
    compact: list[str] = []
    for item in items:
        text = _compact(item, limit=140)
        if text and text not in compact:
            compact.append(text)
        if len(compact) >= limit:
            break
    return compact


def _todo_status(todo: dict[str, Any]) -> str:
    status = str(todo.get("status") or "").strip().lower()
    if status:
        return status
    return "done" if todo.get("done") else "open"


def _is_done(todo: dict[str, Any]) -> bool:
    return bool(todo.get("done")) or _todo_status(todo) in {"done", "archive", "archived"}


def _priority_rank(todo: dict[str, Any]) -> int:
    return _PRIORITY_RANK.get(str(todo.get("priority") or "").strip().upper(), 9)


def _index_rank(todo: dict[str, Any]) -> int:
    try:
        return int(todo.get("index"))
    except (TypeError, ValueError):
        return 999_999


def _todo_sort_key(todo: dict[str, Any]) -> tuple[int, int, int, str]:
    done_rank = 1 if _is_done(todo) else 0
    return (done_rank, _priority_rank(todo), _index_rank(todo), str(todo.get("todo_id") or ""))


def _registered_agents(status_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    run_history = _as_dict(status_payload.get("run_history"))
    for goal in _as_list(run_history.get("goals")):
        if not isinstance(goal, dict):
            continue
        goal_id = _compact(goal.get("id"), limit=180)
        coordination = _as_dict(goal.get("coordination"))
        primary = normalize_todo_claimed_by(coordination.get("primary_agent"))
        for raw_agent in _as_list(coordination.get("registered_agents")):
            agent_id = normalize_todo_claimed_by(raw_agent)
            if not agent_id:
                continue
            row = rows.setdefault(
                agent_id,
                {
                    "agent_id": agent_id,
                    "role": "primary" if agent_id == primary else "side-agent",
                    "_goal_ids": [],
                    "_todos": [],
                },
            )
            if goal_id and goal_id not in row["_goal_ids"]:
                row["_goal_ids"].append(goal_id)
    return rows


def _iter_status_todos(status_payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    queue = _as_dict(status_payload.get("attention_queue"))
    for item in _as_list(queue.get("items")):
        if not isinstance(item, dict):
            continue
        goal_id = _compact(item.get("goal_id"), limit=180)
        for source_name in ("agent_todos",):
            group = _as_dict(item.get(source_name))
            for todo in _as_list(group.get("items")):
                if isinstance(todo, dict):
                    row = dict(todo)
                    row.setdefault("goal_id", goal_id)
                    row.setdefault("source", f"attention_queue.{source_name}")
                    yield row
        project_asset = _as_dict(item.get("project_asset"))
        group = _as_dict(project_asset.get("agent_todos"))
        for todo in _as_list(group.get("items")):
            if isinstance(todo, dict):
                row = dict(todo)
                row.setdefault("goal_id", goal_id)
                row.setdefault("source", "project_asset.agent_todos")
                yield row

    todo_index = _as_dict(status_payload.get("todo_index"))
    for todo in _as_list(todo_index.get("items")):
        if isinstance(todo, dict) and str(todo.get("role") or "") == "agent":
            row = dict(todo)
            row.setdefault("source", "todo_index")
            yield row


def _todo_agent_id(todo: dict[str, Any]) -> str | None:
    return (
        normalize_todo_claimed_by(todo.get("claimed_by"))
        or normalize_todo_claimed_by(todo.get("agent_id"))
    )


def _todo_identity(todo: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(todo.get("goal_id") or ""),
        str(todo.get("todo_id") or ""),
        str(todo.get("index") or ""),
        str(todo.get("text") or todo.get("title") or ""),
    )


def _todo_row(todo: dict[str, Any]) -> dict[str, Any]:
    todo_id = normalize_todo_id(todo.get("todo_id"))
    row: dict[str, Any] = {
        "schema_version": TODO_ROW_SCHEMA_VERSION,
        "todo_id": todo_id,
        "goal_id": _compact(todo.get("goal_id"), limit=180),
        "role": "agent",
        "status": _todo_status(todo),
        "priority": _compact(todo.get("priority"), limit=40),
        "title": _compact(todo.get("title") or todo.get("text"), limit=96),
        "task_class": _compact(todo.get("task_class"), limit=80),
        "action_kind": _compact(todo.get("action_kind"), limit=100),
        "claimed_by": normalize_todo_claimed_by(todo.get("claimed_by")),
    }
    for key in (
        "required_capabilities",
        "required_write_scopes",
        "target_capabilities",
        "blocks_agent",
        "unblocks_todo_id",
        "successor_todo_ids",
        "resume_when",
        "updated_at",
    ):
        value = todo.get(key)
        if value not in (None, "", [], {}):
            row[key] = value
    return {key: value for key, value in row.items() if value not in (None, "", [], {})}


def _workspace_ref_from_todo(todo: dict[str, Any] | None) -> dict[str, Any] | None:
    if not todo:
        return None
    raw = _as_dict(todo.get("workspace_ref"))
    scopes = _string_list(
        raw.get("write_scope")
        or todo.get("required_write_scopes")
        or todo.get("required_write_scope")
    )
    if raw:
        workspace: dict[str, Any] = {
            "kind": _compact(raw.get("kind") or "unknown", limit=80),
            "label": _compact(raw.get("label") or raw.get("branch") or raw.get("kind"), limit=140),
            "path_safe": raw.get("path_safe") is True,
        }
        branch = _compact(raw.get("branch"), limit=120)
        if branch:
            workspace["branch"] = branch
        if scopes:
            workspace["write_scope"] = scopes
        return {key: value for key, value in workspace.items() if value not in (None, "", [], {})}

    policy = _compact(
        todo.get("worktree_policy")
        or todo.get("workspace_policy")
        or todo.get("workspace_kind"),
        limit=120,
    )
    if not (policy or scopes):
        return None
    policy_lower = (policy or "").lower()
    kind = "worktree" if "worktree" in policy_lower else "unknown"
    workspace = {
        "kind": kind,
        "label": policy or "workspace not projected",
        "path_safe": False,
        "write_scope": scopes,
    }
    return {key: value for key, value in workspace.items() if value not in (None, "", [], {})}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _stale_claim_hint(todo: dict[str, Any] | None, *, agent_id: str) -> dict[str, Any] | None:
    if not todo or _is_done(todo):
        return None
    if todo.get("task_class") == "continuous_monitor":
        return None
    claimed_by = (
        normalize_todo_claimed_by(todo.get("claimed_by"))
        or normalize_todo_claimed_by(todo.get("agent_id"))
        or agent_id
    )
    if not claimed_by:
        return None
    last_activity = _compact(todo.get("updated_at") or todo.get("latest_event_at"), limit=80)
    if not last_activity:
        return {
            "state": "activity_missing",
            "claimed_by": claimed_by,
            "reason": "claimed open todo has no projected activity timestamp",
            "recommended_operator_action": "inspect evidence before considering reassignment",
        }
    parsed = _parse_timestamp(last_activity)
    if not parsed:
        return {
            "state": "activity_unparsed",
            "claimed_by": claimed_by,
            "last_activity_at": last_activity,
            "reason": "projected activity timestamp could not be parsed",
            "recommended_operator_action": "inspect status/evidence before considering reassignment",
        }
    age_hours = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours <= STALE_CLAIM_THRESHOLD_HOURS:
        return None
    return {
        "state": "suspected_stale",
        "claimed_by": claimed_by,
        "last_activity_at": last_activity,
        "threshold_hours": STALE_CLAIM_THRESHOLD_HOURS,
        "reason": "last projected activity is older than the stale-claim warning threshold",
        "recommended_operator_action": "ask the same agent to resume or inspect evidence before manual handoff",
    }


def _refs_from_todo(todo: dict[str, Any]) -> tuple[list[str], list[str]]:
    evidence_refs: list[str] = []
    handoff_refs: list[str] = []
    handoff = _as_dict(todo.get("handoff_note"))
    handoff_id = _compact(handoff.get("handoff_id"), limit=140)
    if handoff_id:
        handoff_refs.append(handoff_id)
    for raw_ref in _as_list(handoff.get("evidence_refs")):
        ref = _compact(raw_ref, limit=180)
        if ref and ref not in evidence_refs:
            evidence_refs.append(ref)
    todo_id = normalize_todo_id(todo.get("todo_id"))
    if todo.get("evidence") and todo_id:
        evidence_refs.append(f"todo:{todo_id}:evidence")
    if todo.get("note") and todo_id:
        evidence_refs.append(f"todo:{todo_id}:note")
    latest_event_kind = _compact(todo.get("latest_event_kind"), limit=80)
    if latest_event_kind and todo_id:
        evidence_refs.append(f"rollout_event:{latest_event_kind}:{todo_id}")
    for material in _as_list(todo.get("review_materials")):
        if isinstance(material, dict):
            ref = _compact(material.get("label") or material.get("path"), limit=180)
            if ref:
                evidence_refs.append(ref)
    return evidence_refs[:MAX_REFS], handoff_refs[:MAX_REFS]


def _agent_state(todos: list[dict[str, Any]]) -> str:
    open_todos = [todo for todo in todos if not _is_done(todo)]
    if not open_todos:
        return "waiting" if todos else "unknown"
    if any(_todo_status(todo) == "blocked" or todo.get("task_class") == "blocker" for todo in open_todos):
        return "blocked"
    if any(
        todo.get("task_class") == "continuous_monitor"
        or "monitor" in str(todo.get("action_kind") or "").lower()
        for todo in open_todos
    ):
        return "monitoring"
    return "running"


def _last_activity(todos: list[dict[str, Any]]) -> str | None:
    candidates = [
        _compact(todo.get("updated_at") or todo.get("latest_event_at"), limit=80)
        for todo in todos
    ]
    return sorted([item for item in candidates if item], reverse=True)[0] if any(candidates) else None


def _safe_next_action(todo: dict[str, Any] | None) -> str:
    if not todo:
        return "Inspect status projection before taking work."
    todo_id = normalize_todo_id(todo.get("todo_id"))
    if todo_id:
        return f"Continue projected todo {todo_id}."
    return "Inspect projected todo."


def build_agent_management_projection(status_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a read-only agent management view from a status payload.

    This is a projection over existing LoopX status/todo/history state. It does
    not allocate tasks, dispatch agents, reclaim stale claims, or expose write
    actions.
    """

    rows_by_agent = _registered_agents(status_payload)
    seen_todos: set[tuple[str, str, str, str]] = set()
    for todo in _iter_status_todos(status_payload):
        agent_id = _todo_agent_id(todo)
        if not agent_id:
            continue
        identity = _todo_identity(todo)
        if identity in seen_todos:
            continue
        seen_todos.add(identity)
        row = rows_by_agent.setdefault(
            agent_id,
            {
                "agent_id": agent_id,
                "role": "agent",
                "_goal_ids": [],
                "_todos": [],
            },
        )
        goal_id = _compact(todo.get("goal_id"), limit=180)
        if goal_id and goal_id not in row["_goal_ids"]:
            row["_goal_ids"].append(goal_id)
        row["_todos"].append(todo)

    agents: list[dict[str, Any]] = []
    for agent_id, raw_row in sorted(rows_by_agent.items()):
        todos = sorted(_as_list(raw_row.get("_todos")), key=_todo_sort_key)[:MAX_AGENT_TODOS]
        current = next((todo for todo in todos if not _is_done(todo)), None)
        evidence_refs: list[str] = []
        handoff_refs: list[str] = []
        for todo in todos:
            todo_evidence, todo_handoffs = _refs_from_todo(todo)
            for ref in todo_evidence:
                if ref not in evidence_refs:
                    evidence_refs.append(ref)
            for ref in todo_handoffs:
                if ref not in handoff_refs:
                    handoff_refs.append(ref)
        agent_row: dict[str, Any] = {
            "agent_id": agent_id,
            "role": raw_row.get("role") or "agent",
            "state": _agent_state(todos),
            "current_todo": _todo_row(current) if current else None,
            "next_action": _safe_next_action(current),
            "last_activity_at": _last_activity(todos),
            "evidence_refs": evidence_refs[:MAX_REFS],
            "handoff_refs": handoff_refs[:MAX_REFS],
            "goal_ids": _as_list(raw_row.get("_goal_ids"))[:MAX_REFS],
        }
        workspace_ref = _workspace_ref_from_todo(current)
        if workspace_ref:
            agent_row["workspace_ref"] = workspace_ref
        stale_claim_hint = _stale_claim_hint(current, agent_id=agent_id)
        if stale_claim_hint:
            agent_row["stale_claim_hint"] = stale_claim_hint
        agents.append(
            {
                key: value
                for key, value in agent_row.items()
                if value not in (None, "", [], {})
            }
        )
        if len(agents) >= MAX_AGENT_ROWS:
            break

    goal_filter = _compact(status_payload.get("goal_filter"), limit=180)
    projection: dict[str, Any] = {
        "schema_version": AGENT_MANAGEMENT_PROJECTION_SCHEMA_VERSION,
        "mode": AGENT_MANAGEMENT_MODE,
        "goal_id": goal_filter,
        "generated_at": _now_iso(),
        "truth_contract": {
            "todo_is_runtime_work_item": True,
            "projection_is_writable": False,
            "introduces_task_runtime": False,
            "write_api": False,
        },
        "source_summary": {
            "registered_agent_count": len(rows_by_agent),
            "projected_agent_count": len(agents),
            "todo_source": "status.attention_queue + status.todo_index",
        },
        "agents": agents,
    }
    return {
        key: value
        for key, value in projection.items()
        if value not in (None, "", [], {})
    }
