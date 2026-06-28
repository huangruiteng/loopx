from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Callable


TASK_GRAPH_PROJECTION_SCHEMA_VERSION = "task_graph_projection_v0"
TASK_GRAPH_SOURCE_OF_TRUTH = [
    "event_ledger",
    "active_goal_state",
    "todos",
    "gates",
    "leases",
    "run_history",
]
TASK_GRAPH_MAX_USER_GATE_NODES = 2
TASK_GRAPH_AUDIT_MARKERS = ("audit", "audited")
TASK_GRAPH_CONTINUATION_MARKERS = ("continuation", "continue", "continuing", "continued")


def _task_graph_safe_id(
    prefix: str,
    value: Any,
    *,
    public_safe_compact_text: Callable[..., str | None],
) -> str:
    raw = public_safe_compact_text(value, limit=120) or prefix
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_").lower()
    if not normalized:
        normalized = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:10]
    if len(normalized) > 56:
        suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
        normalized = f"{normalized[:47].rstrip('_')}_{suffix}"
    return f"{prefix}_{normalized}"


def _task_graph_ref_values(
    *values: Any,
    limit: int = 4,
    public_safe_compact_text: Callable[..., str | None],
) -> list[str]:
    refs: list[str] = []
    for value in values:
        if isinstance(value, list):
            for nested in _task_graph_ref_values(
                *value,
                limit=limit,
                public_safe_compact_text=public_safe_compact_text,
            ):
                if nested not in refs:
                    refs.append(nested)
                    if len(refs) >= limit:
                        return refs
            continue
        text = public_safe_compact_text(value, limit=120)
        if not text or text in refs:
            continue
        refs.append(text)
        if len(refs) >= limit:
            break
    return refs


def _task_graph_refs(
    key: str,
    *values: Any,
    public_safe_compact_text: Callable[..., str | None],
) -> dict[str, list[str]] | None:
    refs = _task_graph_ref_values(*values, public_safe_compact_text=public_safe_compact_text)
    if not refs:
        return None
    return {key: refs}


def _task_graph_todo_state(
    todo: dict[str, Any],
    *,
    normalize_todo_status: Callable[[Any], str | None],
    todo_done_for_status: Callable[[str], bool],
    todo_status_open: str,
    waiting_default: bool = False,
) -> str:
    status = normalize_todo_status(todo.get("status")) or todo_status_open
    if todo.get("done") or todo_done_for_status(status):
        return "done"
    if status == "blocked":
        return "blocked"
    if status in {"waiting", "deferred"} or waiting_default:
        return "waiting"
    return "open"


def _task_graph_generated_at(
    *,
    goal: dict[str, Any],
    goal_latest_runs: list[dict[str, Any]],
    public_safe_compact_text: Callable[..., str | None],
    latest_run: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> str:
    candidates: list[dict[str, Any]] = [*goal_latest_runs]
    current_run = latest_run(goal)
    if isinstance(current_run, dict):
        candidates.append(current_run)
    for run in candidates:
        generated_at = public_safe_compact_text(run.get("generated_at"), limit=80)
        if generated_at:
            return generated_at
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _task_graph_active_state_updated_at(
    item: dict[str, Any],
    goal: dict[str, Any],
    *,
    public_safe_compact_text: Callable[..., str | None],
    latest_run: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> str | None:
    warning = (
        item.get("stale_latest_run_warning")
        if isinstance(item.get("stale_latest_run_warning"), dict)
        else {}
    )
    updated_at = public_safe_compact_text(warning.get("active_state_updated_at"), limit=80)
    if updated_at:
        return updated_at
    current_run = latest_run(goal)
    state = (
        current_run.get("state")
        if isinstance(current_run, dict) and isinstance(current_run.get("state"), dict)
        else {}
    )
    frontmatter = state.get("frontmatter") if isinstance(state.get("frontmatter"), dict) else {}
    return public_safe_compact_text(frontmatter.get("updated_at"), limit=80)


def _task_graph_latest_run_node(
    *,
    goal_latest_runs: list[dict[str, Any]],
    selected_todo_id: str | None,
    public_safe_compact_text: Callable[..., str | None],
) -> dict[str, Any] | None:
    for run in goal_latest_runs:
        if not isinstance(run, dict):
            continue
        run_ref = public_safe_compact_text(
            run.get("run_id") or run.get("generated_at") or run.get("classification"),
            limit=120,
        )
        classification = public_safe_compact_text(run.get("classification"), limit=120)
        if not (run_ref or classification):
            continue
        refs = _task_graph_refs(
            "run_ids",
            run_ref or classification,
            public_safe_compact_text=public_safe_compact_text,
        )
        if refs and selected_todo_id:
            todo_refs = _task_graph_ref_values(
                selected_todo_id,
                public_safe_compact_text=public_safe_compact_text,
            )
            if todo_refs:
                refs["todo_ids"] = todo_refs
        if not refs:
            continue
        title = classification or "Latest compact run-history evidence"
        return {
            "node_id": _task_graph_safe_id(
                "node_run",
                run_ref or title,
                public_safe_compact_text=public_safe_compact_text,
            ),
            "kind": "validation",
            "title": f"Latest compact run: {title}",
            "state": "ready",
            "refs": refs,
        }
    return None


def _task_graph_latest_run_lineage_relations(
    run_node_id: str | None,
    selected_node_id: str | None,
    *,
    goal_latest_runs: list[dict[str, Any]],
    public_safe_compact_text: Callable[..., str | None],
) -> list[tuple[str, str]]:
    if not run_node_id or not selected_node_id:
        return []
    for run in goal_latest_runs:
        if not isinstance(run, dict):
            continue
        values = [
            run.get("classification"),
            run.get("recommended_action"),
            run.get("delivery_outcome"),
            run.get("delivery_batch_scale"),
        ]
        text = " ".join(
            public_safe_compact_text(value, limit=160) or ""
            for value in values
        ).lower()
        if not text.strip():
            continue
        relations: list[tuple[str, str]] = []
        if any(marker in text for marker in TASK_GRAPH_AUDIT_MARKERS):
            relations.append(
                (
                    "audits",
                    "Compact run-history evidence audits the selected work lane without replacing todo or gate state.",
                )
            )
        if any(marker in text for marker in TASK_GRAPH_CONTINUATION_MARKERS):
            relations.append(
                (
                    "continues",
                    "Compact run-history evidence records a continuation of the selected work lane.",
                )
            )
        return relations
    return []


def _task_graph_visible_user_gate_items(
    user_todos: dict[str, Any] | None,
    *,
    limit: int,
    open_todo_items: Callable[..., list[dict[str, Any]]],
    max_status_todos_per_role: int,
    todo_item_task_class: Callable[[dict[str, Any]], str],
    user_gate_task_class: str,
    todo_summary_open_count: Callable[[dict[str, Any] | None], int],
) -> tuple[list[dict[str, Any]], int]:
    visible_items = open_todo_items(
        user_todos,
        limit=max_status_todos_per_role,
        text_limit=180,
        source_keys=("gate_open_items", "first_open_items", "items"),
    )
    visible_gate_items = [
        item for item in visible_items if todo_item_task_class(item) == user_gate_task_class
    ]
    if visible_gate_items and len(visible_gate_items) == len(visible_items):
        gate_open_count = max(len(visible_gate_items), todo_summary_open_count(user_todos))
    else:
        gate_open_count = len(visible_gate_items)
    return visible_gate_items[:limit], gate_open_count


def build_task_graph_projection(
    item: dict[str, Any],
    *,
    goal: dict[str, Any],
    goal_latest_runs: list[dict[str, Any]] | None = None,
    public_safe_compact_text: Callable[..., str | None],
    normalize_todo_status: Callable[[Any], str | None],
    todo_done_for_status: Callable[[str], bool],
    todo_status_open: str,
    open_todo_items: Callable[..., list[dict[str, Any]]],
    max_status_todos_per_role: int,
    todo_item_task_class: Callable[[dict[str, Any]], str],
    user_gate_task_class: str,
    todo_summary_open_count: Callable[[dict[str, Any] | None], int],
    latest_run: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> dict[str, Any] | None:
    """Build a compact read-only graph from already-projected status fields."""

    goal_id = public_safe_compact_text(item.get("goal_id") or goal.get("id"), limit=120)
    if not goal_id:
        return None
    latest_runs = [run for run in goal_latest_runs or [] if isinstance(run, dict)]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    edge_ids: set[str] = set()
    refs_by_node_id: dict[str, dict[str, list[str]]] = {}

    def add_node(node: dict[str, Any] | None) -> str | None:
        if not isinstance(node, dict):
            return None
        node_id = str(node.get("node_id") or "")
        if not node_id:
            return None
        if node_id in node_ids:
            return node_id
        refs = node.get("refs") if isinstance(node.get("refs"), dict) else None
        if not refs:
            return None
        title = public_safe_compact_text(node.get("title"), limit=160)
        if not title:
            return None
        node["title"] = title
        node_ids.add(node_id)
        refs_by_node_id[node_id] = refs
        nodes.append(node)
        return node_id

    def add_edge(
        *,
        edge_id: str,
        from_node_id: str | None,
        to_node_id: str | None,
        relation: str,
        reason: str,
        refs: dict[str, list[str]] | None = None,
    ) -> None:
        if not from_node_id or not to_node_id or from_node_id == to_node_id:
            return
        if from_node_id not in node_ids or to_node_id not in node_ids or edge_id in edge_ids:
            return
        compact_reason = public_safe_compact_text(reason, limit=180)
        if not compact_reason:
            return
        edge: dict[str, Any] = {
            "edge_id": edge_id,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "relation": relation,
            "reason": compact_reason,
        }
        if refs:
            edge["refs"] = refs
        edge_ids.add(edge_id)
        edges.append(edge)

    agent_items = open_todo_items(
        item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None,
        limit=1,
        text_limit=180,
    )
    selected_todo = agent_items[0] if agent_items else None
    selected_todo_id = public_safe_compact_text(
        selected_todo.get("todo_id") if isinstance(selected_todo, dict) else None,
        limit=120,
    )
    selected_node_id: str | None = None
    if isinstance(selected_todo, dict):
        selected_node_id = add_node(
            {
                "node_id": _task_graph_safe_id(
                    "node_todo",
                    selected_todo_id or selected_todo.get("text"),
                    public_safe_compact_text=public_safe_compact_text,
                ),
                "kind": "deliverable",
                "title": selected_todo.get("title") or selected_todo.get("text"),
                "state": _task_graph_todo_state(
                    selected_todo,
                    normalize_todo_status=normalize_todo_status,
                    todo_done_for_status=todo_done_for_status,
                    todo_status_open=todo_status_open,
                ),
                "refs": _task_graph_refs(
                    "todo_ids",
                    selected_todo_id,
                    public_safe_compact_text=public_safe_compact_text,
                ),
                **(
                    {"owner_agent": selected_todo.get("claimed_by")}
                    if public_safe_compact_text(selected_todo.get("claimed_by"), limit=80)
                    else {}
                ),
            }
        )
        claimed_by = public_safe_compact_text(selected_todo.get("claimed_by"), limit=80)
        if claimed_by and selected_node_id:
            lease_id = f"claim:{goal_id}:{selected_todo_id or 'selected'}:{claimed_by}"
            lease_node_id = add_node(
                {
                    "node_id": _task_graph_safe_id(
                        "node_lease",
                        lease_id,
                        public_safe_compact_text=public_safe_compact_text,
                    ),
                    "kind": "lease",
                    "title": f"Claimed by {claimed_by}",
                    "state": "ready",
                    "refs": _task_graph_refs(
                        "lease_ids",
                        lease_id,
                        public_safe_compact_text=public_safe_compact_text,
                    ),
                    "owner_agent": claimed_by,
                }
            )
            add_edge(
                edge_id=_task_graph_safe_id(
                    "edge_depends",
                    f"{selected_node_id}:{lease_node_id}",
                    public_safe_compact_text=public_safe_compact_text,
                ),
                from_node_id=selected_node_id,
                to_node_id=lease_node_id,
                relation="depends_on",
                reason="Selected work depends on its active claim lease.",
                refs=_task_graph_refs(
                    "lease_ids",
                    lease_id,
                    public_safe_compact_text=public_safe_compact_text,
                ),
            )

    user_todo_summary = item.get("user_todos") if isinstance(item.get("user_todos"), dict) else None
    user_items, user_gate_open_count = _task_graph_visible_user_gate_items(
        user_todo_summary,
        limit=TASK_GRAPH_MAX_USER_GATE_NODES,
        open_todo_items=open_todo_items,
        max_status_todos_per_role=max_status_todos_per_role,
        todo_item_task_class=todo_item_task_class,
        user_gate_task_class=user_gate_task_class,
        todo_summary_open_count=todo_summary_open_count,
    )
    for ordinal, todo in enumerate(user_items):
        todo_id = public_safe_compact_text(todo.get("todo_id"), limit=120)
        gate_id = todo_id or f"gate:{goal_id}:user:{ordinal + 1}"
        gate_node_id = add_node(
            {
                "node_id": _task_graph_safe_id(
                    "node_gate",
                    gate_id,
                    public_safe_compact_text=public_safe_compact_text,
                ),
                "kind": "gate",
                "title": todo.get("title") or todo.get("text") or "Open user gate",
                "state": _task_graph_todo_state(
                    todo,
                    normalize_todo_status=normalize_todo_status,
                    todo_done_for_status=todo_done_for_status,
                    todo_status_open=todo_status_open,
                    waiting_default=True,
                ),
                "refs": _task_graph_refs(
                    "gate_ids",
                    gate_id,
                    public_safe_compact_text=public_safe_compact_text,
                ),
            }
        )
        add_edge(
            edge_id=_task_graph_safe_id(
                "edge_blocks",
                f"{gate_node_id}:{selected_node_id}:{ordinal}",
                public_safe_compact_text=public_safe_compact_text,
            ),
            from_node_id=gate_node_id,
            to_node_id=selected_node_id,
            relation="blocks",
            reason="Open user gate blocks the gated delivery path.",
            refs=_task_graph_refs(
                "gate_ids",
                gate_id,
                public_safe_compact_text=public_safe_compact_text,
            ),
        )
    user_gate_truncated_count = max(0, user_gate_open_count - len(user_items))
    if user_gate_truncated_count:
        summary_node_id = add_node(
            {
                "node_id": _task_graph_safe_id(
                    "node_gate_summary",
                    f"{goal_id}:{user_gate_truncated_count}:more_user_gates",
                    public_safe_compact_text=public_safe_compact_text,
                ),
                "kind": "gate_summary",
                "title": f"{user_gate_truncated_count} more open user gates not expanded",
                "state": "waiting",
                "refs": _task_graph_refs(
                    "goal_ids",
                    goal_id,
                    public_safe_compact_text=public_safe_compact_text,
                ),
            }
        )
        add_edge(
            edge_id=_task_graph_safe_id(
                "edge_blocks",
                f"{summary_node_id}:{selected_node_id}:user_gate_summary",
                public_safe_compact_text=public_safe_compact_text,
            ),
            from_node_id=summary_node_id,
            to_node_id=selected_node_id,
            relation="blocks",
            reason="Additional open user gates stay on the cold path instead of expanding the task graph hot path.",
            refs=_task_graph_refs(
                "goal_ids",
                goal_id,
                public_safe_compact_text=public_safe_compact_text,
            ),
        )

    run_node_id = add_node(
        _task_graph_latest_run_node(
            goal_latest_runs=latest_runs,
            selected_todo_id=selected_todo_id,
            public_safe_compact_text=public_safe_compact_text,
        )
    )
    add_edge(
        edge_id=_task_graph_safe_id(
            "edge_validates",
            f"{run_node_id}:{selected_node_id}",
            public_safe_compact_text=public_safe_compact_text,
        ),
        from_node_id=run_node_id,
        to_node_id=selected_node_id,
        relation="validates",
        reason="Latest compact run-history evidence validates or contextualizes the selected work.",
        refs=refs_by_node_id.get(run_node_id or ""),
    )
    for relation, reason in _task_graph_latest_run_lineage_relations(
        run_node_id,
        selected_node_id,
        goal_latest_runs=latest_runs,
        public_safe_compact_text=public_safe_compact_text,
    ):
        add_edge(
            edge_id=_task_graph_safe_id(
                f"edge_{relation}",
                f"{run_node_id}:{selected_node_id}",
                public_safe_compact_text=public_safe_compact_text,
            ),
            from_node_id=run_node_id,
            to_node_id=selected_node_id,
            relation=relation,
            reason=reason,
            refs=refs_by_node_id.get(run_node_id or ""),
        )

    replan = (
        item.get("autonomous_replan_obligation")
        if isinstance(item.get("autonomous_replan_obligation"), dict)
        else None
    )
    if replan and selected_node_id:
        replan_id = public_safe_compact_text(
            replan.get("schema_version") or replan.get("kind") or "autonomous_replan_obligation",
            limit=120,
        )
        repair_node_id = add_node(
            {
                "node_id": _task_graph_safe_id(
                    "node_repair",
                    replan_id,
                    public_safe_compact_text=public_safe_compact_text,
                ),
                "kind": "repair",
                "title": replan.get("recommended_action") or replan_id,
                "state": "ready",
                "refs": _task_graph_refs(
                    "todo_ids",
                    selected_todo_id,
                    public_safe_compact_text=public_safe_compact_text,
                ),
            }
        )
        add_edge(
            edge_id=_task_graph_safe_id(
                "edge_repairs",
                f"{repair_node_id}:{selected_node_id}",
                public_safe_compact_text=public_safe_compact_text,
            ),
            from_node_id=repair_node_id,
            to_node_id=selected_node_id,
            relation="repairs",
            reason="Autonomous repair/replan obligation should recover the selected work lane.",
            refs=_task_graph_refs(
                "todo_ids",
                selected_todo_id,
                public_safe_compact_text=public_safe_compact_text,
            ),
        )

    if not nodes:
        return None
    derived_from: dict[str, Any] = {
        "source_of_truth": TASK_GRAPH_SOURCE_OF_TRUTH,
        "status_item_goal_id": goal_id,
        "run_history_window": "compact_latest_runs",
    }
    active_state_updated_at = _task_graph_active_state_updated_at(
        item,
        goal,
        public_safe_compact_text=public_safe_compact_text,
        latest_run=latest_run,
    )
    if active_state_updated_at:
        derived_from["active_state_updated_at"] = active_state_updated_at
    return {
        "schema_version": TASK_GRAPH_PROJECTION_SCHEMA_VERSION,
        "mode": "read_only",
        "goal_id": goal_id,
        "generated_at": _task_graph_generated_at(
            goal=goal,
            goal_latest_runs=latest_runs,
            public_safe_compact_text=public_safe_compact_text,
            latest_run=latest_run,
        ),
        "derived_from": derived_from,
        "truth_contract": {
            "event_ledger_is_source_of_truth": True,
            "projection_is_writable": False,
            "write_api": False,
            "recompute_rule": "Recompute from status, active state, gates, leases, and run history after each lifecycle event.",
        },
        "limits": {
            "user_gate_node_limit": TASK_GRAPH_MAX_USER_GATE_NODES,
            "user_gate_open_count": user_gate_open_count,
            "user_gate_truncated_count": user_gate_truncated_count,
        },
        "nodes": nodes,
        "edges": edges,
    }
