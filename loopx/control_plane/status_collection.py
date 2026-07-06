from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


StatusCallback = Callable[..., Any]


@dataclass(frozen=True)
class StatusCollectionContext:
    load_registry: StatusCallback
    resolve_runtime_root: StatusCallback
    collect_global_registry_health: StatusCallback
    collect_history: StatusCallback
    check_contract: StatusCallback
    build_attention_queue: StatusCallback
    build_run_history: StatusCallback
    build_event_ledger_summary: StatusCallback
    build_promotion_readiness_summary: StatusCallback
    build_promotion_gate: StatusCallback
    build_decision_freshness_summary: StatusCallback
    build_usage_summary: StatusCallback
    build_todo_index: StatusCallback
    build_status_contract: StatusCallback
    build_contract_health_projection: StatusCallback
    build_agent_management_projection: StatusCallback
    status_control_plane_context_limit: int
    max_todo_index_items: int


def collect_status(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    limit: int,
    context: StatusCollectionContext,
    include_task_graph: bool = False,
    goal_id: str | None = None,
) -> dict[str, Any]:
    display_limit = max(0, limit)
    control_plane_limit = max(display_limit, context.status_control_plane_context_limit)
    goal_filter = str(goal_id or "").strip() or None
    registry = context.load_registry(registry_path)
    runtime_root = context.resolve_runtime_root(registry, runtime_root_override)
    global_registry = context.collect_global_registry_health(
        registry_path=registry_path,
        runtime_root=runtime_root,
        current_registry=registry,
    )
    include_runtime_goals = bool(global_registry.get("current_registry_is_global"))
    history = context.collect_history(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=goal_filter,
        limit=control_plane_limit,
        include_runtime_goals=include_runtime_goals,
    )
    contract = context.check_contract(
        registry_path=registry_path,
        runtime_root_override=runtime_root_override,
        scan_roots=scan_roots,
        limit=limit,
    )
    queue = context.build_attention_queue(
        contract=contract,
        history=history,
        global_registry=global_registry,
        runtime_root=runtime_root,
        include_task_graph=include_task_graph,
        goal_id_filter=goal_filter,
    )
    run_history = context.build_run_history(history, display_limit=display_limit)
    event_ledger_summary = context.build_event_ledger_summary(history)
    promotion_readiness_summary = context.build_promotion_readiness_summary(
        history,
        runtime_root=runtime_root,
        goal_id_filter=goal_filter,
    )
    promotion_gate = context.build_promotion_gate(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
    )
    decision_freshness_summary = context.build_decision_freshness_summary(history)
    usage_summary = context.build_usage_summary(history)
    todo_index = context.build_todo_index(
        queue=queue,
        history=history,
        runtime_root=runtime_root,
        limit=max(context.max_todo_index_items, display_limit),
    )
    payload = {
        "ok": bool(contract.get("ok")) and bool(global_registry.get("ok", True)),
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "status_contract": context.build_status_contract(),
        "goal_filter": goal_filter,
        **context.build_contract_health_projection(contract),
        "contract": {
            "ok": contract.get("ok"),
            "summary": contract.get("summary"),
            "errors": contract.get("errors") or [],
            "warnings": contract.get("warnings") or [],
            "checks": contract.get("checks") or [],
        },
        "global_registry": global_registry,
        "attention_queue": queue,
        "run_history": run_history,
        "event_ledger_summary": event_ledger_summary,
        "promotion_readiness_summary": promotion_readiness_summary,
        "promotion_gate": promotion_gate,
        "decision_freshness_summary": decision_freshness_summary,
        "usage_summary": usage_summary,
        "todo_index": todo_index,
    }
    agent_management_projection = context.build_agent_management_projection(payload)
    if agent_management_projection.get("agents"):
        payload["agent_management_projection"] = agent_management_projection
    return payload
