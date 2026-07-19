from __future__ import annotations

from typing import Any

from ..todos.contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    normalize_required_capabilities,
    normalize_target_capabilities,
    normalize_todo_claimed_by,
)
from ..todos.projection import (
    todo_index_rank,
    todo_item_is_actionable_open,
    todo_item_task_class,
    todo_priority_rank,
)
from ..todos.summary_item import compact_todo_summary_item
from .agent_scope import agent_scope_item_claimed_by
from .profile import agent_profile_candidate_rank


CAPABILITY_GATE_SCHEMA_VERSION = "capability_gate_v0"
DEFAULT_AVAILABLE_CAPABILITIES = (
    "shell",
    "filesystem_read",
    "filesystem_write",
)
CAPABILITY_REPAIR_BRIDGE_HINTS = {
    "benchmark_runner",
    "network",
    "external_evidence_poll",
    "worker_bridge",
    "cli_bridge",
}
CAPABILITY_OWNER_GATE_HINTS = {
    "credentials",
    "production_access",
}


def runtime_capabilities_for_cli_projection(value: Any) -> list[str]:
    """Return observed runtime capabilities, never owner-held authority gates."""

    return [
        capability
        for capability in normalize_required_capabilities(value)
        if capability not in CAPABILITY_OWNER_GATE_HINTS
    ]


def _capability_missing_action(missing: list[str]) -> str:
    missing_set = set(missing)
    if not missing_set:
        return "run"
    if missing_set & CAPABILITY_OWNER_GATE_HINTS:
        return "ask_owner"
    if missing_set & CAPABILITY_REPAIR_BRIDGE_HINTS:
        return "repair_bridge"
    return "skip"


def _capability_resolution(missing: list[str]) -> dict[str, Any]:
    owner_missing = [
        capability
        for capability in missing
        if capability in CAPABILITY_OWNER_GATE_HINTS
    ]
    repair_missing = [
        capability
        for capability in missing
        if capability in CAPABILITY_REPAIR_BRIDGE_HINTS
    ]
    unsupported_missing = [
        capability
        for capability in missing
        if capability not in CAPABILITY_OWNER_GATE_HINTS
        and capability not in CAPABILITY_REPAIR_BRIDGE_HINTS
    ]
    action = _capability_missing_action(missing)
    decision_owner = (
        "user"
        if action == "ask_owner"
        else "agent"
        if action == "repair_bridge"
        else "capability_gate"
    )
    resolution_steps: list[dict[str, Any]] = []
    if owner_missing:
        resolution_steps.append(
            {
                "owner": "user",
                "action": "provide_or_authorize",
                "capabilities": owner_missing,
            }
        )
    if repair_missing:
        resolution_steps.append(
            {
                "owner": "agent",
                "action": "repair_bridge",
                "capabilities": repair_missing,
            }
        )
    if unsupported_missing:
        resolution_steps.append(
            {
                "owner": "capability_gate",
                "action": "unsupported",
                "capabilities": unsupported_missing,
            }
        )
    return {
        "action": action,
        "decision_owner": decision_owner,
        "owner_missing": owner_missing,
        "repair_missing": repair_missing,
        "unsupported_missing": unsupported_missing,
        "resolution_steps": resolution_steps,
    }


def _capability_priority(value: Any) -> str:
    priority = str(value or "").strip().upper()
    for prefix in ("P0", "P1", "P2"):
        if priority.startswith(prefix):
            return prefix
    return "P1"


def _blocked_capability_resolution_bindings(
    blocked: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bindings: dict[tuple[str, str], dict[str, Any]] = {}
    for item in blocked:
        todo_id = str(item.get("todo_id") or "").strip()
        for capability in normalize_required_capabilities(
            item.get("missing_capabilities")
        ):
            action = _capability_missing_action([capability])
            if action == "ask_owner":
                owner = "user"
                resolution_action = "provide_or_authorize"
            elif action == "repair_bridge":
                owner = "agent"
                resolution_action = "repair_bridge"
            else:
                owner = "capability_gate"
                resolution_action = "unsupported"
            key = (owner, capability)
            binding = bindings.get(key)
            if binding is None:
                binding = {
                    "owner": owner,
                    "action": resolution_action,
                    "capability": capability,
                    "priority": _capability_priority(item.get("priority")),
                    "primary_blocked_todo_id": todo_id or None,
                    "blocked_todo_ids": [],
                }
                bindings[key] = binding
            if todo_id and todo_id not in binding["blocked_todo_ids"]:
                binding["blocked_todo_ids"].append(todo_id)
    return list(bindings.values())


def _binding_capabilities(
    bindings: list[dict[str, Any]],
    *,
    owner: str,
) -> list[str]:
    result: list[str] = []
    for binding in bindings:
        if binding.get("owner") != owner:
            continue
        capability = str(binding.get("capability") or "").strip()
        if capability and capability not in result:
            result.append(capability)
    return result


def _owner_capability_action(bindings: list[dict[str, Any]]) -> str | None:
    actions: list[str] = []
    for binding in bindings:
        if binding.get("owner") != "user":
            continue
        capability = str(binding.get("capability") or "").strip()
        todo_id = str(binding.get("primary_blocked_todo_id") or "").strip()
        if capability:
            actions.append(f"{capability} for {todo_id}" if todo_id else capability)
    if not actions:
        return None
    return "provide or authorize the missing owner-held capability: " + ", ".join(
        actions
    )


def available_capabilities_with_defaults(value: Any) -> list[str]:
    capabilities = list(DEFAULT_AVAILABLE_CAPABILITIES)
    for capability in normalize_required_capabilities(value):
        if capability not in capabilities:
            capabilities.append(capability)
    return capabilities


def missing_required_capabilities(
    item: dict[str, Any],
    *,
    available_capabilities: Any,
) -> list[str]:
    available = set(available_capabilities_with_defaults(available_capabilities))
    required = normalize_required_capabilities(item.get("required_capabilities"))
    targets = set(normalize_target_capabilities(item.get("target_capabilities")))
    return [
        capability
        for capability in required
        if capability not in targets and capability not in available
    ]


def _capability_item_identity(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("todo_id") or ""),
        str(item.get("text") or "").strip(),
    )


def _capability_candidate_item(
    item: dict[str, Any],
    *,
    missing: list[str],
    missing_target_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    text = str(item.get("text") or "").strip()
    payload = compact_todo_summary_item(item, text=text)
    required = normalize_required_capabilities(item.get("required_capabilities"))
    targets = normalize_target_capabilities(item.get("target_capabilities"))
    payload["required_capabilities"] = required
    if targets:
        payload["target_capabilities"] = targets
    payload["missing_capabilities"] = missing
    payload["capability_action"] = _capability_missing_action(missing)
    missing_targets = normalize_target_capabilities(missing_target_capabilities)
    if missing_targets:
        payload["missing_target_capabilities"] = missing_targets
    if missing_targets and set(missing_targets) & CAPABILITY_REPAIR_BRIDGE_HINTS:
        payload["capability_repair_mode"] = True
        payload["capability_action"] = "repair_bridge"
    return payload


def _agent_lane_candidate_sort_key(
    raw_item: dict[str, Any],
    *,
    agent_id: str | None,
    preferred_todo_ids: set[str] | None = None,
    agent_profile: dict[str, Any] | None = None,
) -> tuple[int, int, int, int, int, int]:
    preferred_todo_ids = preferred_todo_ids or set()
    todo_id = str(raw_item.get("todo_id") or "").strip()
    active_next_rank = 0 if todo_id and todo_id in preferred_todo_ids else 1
    claimed_by = agent_scope_item_claimed_by(raw_item)
    claim_rank = 0 if agent_id and claimed_by == agent_id else 1
    repair_rank = 0 if raw_item.get("capability_repair_mode") is True else 1
    # Durable Next Action is a steering hint inside the selected peer/profile
    # priority bucket, not permission to cross an explicit todo priority boundary.
    return (
        claim_rank,
        agent_profile_candidate_rank(raw_item, agent_profile=agent_profile),
        todo_priority_rank(raw_item),
        active_next_rank,
        repair_rank,
        todo_index_rank(raw_item),
    )


def _sort_capability_runnable_candidates(
    runnable: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(agent_identity, dict):
        return runnable, None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return runnable, None
    agent_profile = (
        agent_identity.get("agent_profile")
        if isinstance(agent_identity.get("agent_profile"), dict)
        else None
    )
    policy = (
        "claim_then_profile_then_priority_then_active_next_then_repair"
        if agent_profile
        else "claim_then_priority_then_active_next_then_repair"
    )
    return (
        sorted(
            runnable,
            key=lambda item: _agent_lane_candidate_sort_key(
                item,
                agent_id=agent_id,
                agent_profile=agent_profile,
            ),
        ),
        policy,
    )


def _select_advancement_candidate_source(
    agent_todo_summary: dict[str, Any],
) -> tuple[list[Any], str]:
    active_next_items = agent_todo_summary.get("active_next_action_executable_items")
    backlog_items = agent_todo_summary.get("executable_backlog_items")
    first_executable_items = agent_todo_summary.get("first_executable_items")
    if isinstance(active_next_items, list) and active_next_items:
        return (
            [
                *active_next_items,
                *(backlog_items if isinstance(backlog_items, list) else []),
            ],
            "agent_todo_summary.active_next_action_executable_items",
        )
    if isinstance(backlog_items, list) and backlog_items:
        return backlog_items, "agent_todo_summary.executable_backlog_items"
    if isinstance(first_executable_items, list) and first_executable_items:
        return first_executable_items, "agent_todo_summary.first_executable_items"
    return [], "agent_todo_summary.executable_backlog_items"


def _collect_capability_gate_candidates(
    agent_todo_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    raw_items, source = _select_advancement_candidate_source(agent_todo_summary)
    due_monitor_items = (
        agent_todo_summary.get("monitor_due_items")
        if isinstance(agent_todo_summary.get("monitor_due_items"), list)
        else []
    )
    blocked_due_monitor_items = (
        agent_todo_summary.get("monitor_capability_blocked_due_items")
        if isinstance(
            agent_todo_summary.get("monitor_capability_blocked_due_items"), list
        )
        else []
    )
    monitor_sources: list[str] = []
    if due_monitor_items:
        monitor_sources.append("agent_todo_summary.monitor_due_items")
    if blocked_due_monitor_items:
        monitor_sources.append(
            "agent_todo_summary.monitor_capability_blocked_due_items"
        )
    if monitor_sources:
        source_parts = [source, *monitor_sources] if raw_items else monitor_sources
        source = "+".join(source_parts)
        raw_items = [*raw_items, *due_monitor_items, *blocked_due_monitor_items]

    deduped_items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        identity = _capability_item_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        deduped_items.append(item)

    due_monitor_identities = {
        _capability_item_identity(item)
        for item in [*due_monitor_items, *blocked_due_monitor_items]
        if isinstance(item, dict)
    }
    return (
        [
            item
            for item in deduped_items
            if todo_item_is_actionable_open(item)
            and (
                todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
                or _capability_item_identity(item) in due_monitor_identities
            )
        ],
        source,
    )


def _match_capability_candidates(
    candidates: list[dict[str, Any]],
    *,
    available_capabilities: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    blocked: list[dict[str, Any]] = []
    runnable: list[dict[str, Any]] = []
    saw_requirement = False
    for item in candidates:
        required = normalize_required_capabilities(item.get("required_capabilities"))
        targets = normalize_target_capabilities(item.get("target_capabilities"))
        saw_requirement = saw_requirement or bool(required or targets)
        missing = missing_required_capabilities(
            item,
            available_capabilities=available_capabilities,
        )
        if missing:
            blocked.append(_capability_candidate_item(item, missing=missing))
            continue
        missing_targets = [
            capability
            for capability in targets
            if capability not in available_capabilities
        ]
        runnable.append(
            _capability_candidate_item(
                item,
                missing=[],
                missing_target_capabilities=missing_targets,
            )
        )
    return blocked, runnable, saw_requirement


def _unique_candidate_values(
    candidates: list[dict[str, Any]],
    field: str,
) -> list[str]:
    values: list[str] = []
    for item in candidates:
        for value in item.get(field) or []:
            normalized = str(value)
            if normalized not in values:
                values.append(normalized)
    return values


def _build_runnable_capability_gate(
    *,
    source: str,
    available: list[str],
    blocked: list[dict[str, Any]],
    runnable: list[dict[str, Any]],
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    runnable, candidate_order_policy = _sort_capability_runnable_candidates(
        runnable,
        agent_identity=agent_identity,
    )
    resolution_bindings = _blocked_capability_resolution_bindings(blocked)
    repair_missing = _unique_candidate_values(
        [item for item in runnable if item.get("capability_repair_mode") is True],
        "missing_target_capabilities",
    )
    for capability in _binding_capabilities(resolution_bindings, owner="agent"):
        if capability not in repair_missing:
            repair_missing.append(capability)
    return {
        "schema_version": CAPABILITY_GATE_SCHEMA_VERSION,
        "source": source,
        "required": _unique_candidate_values(runnable, "required_capabilities"),
        "available": available,
        "missing": [],
        "action": "run",
        "decision_owner": "agent",
        "selection_policy": "agent_steering_audit_over_runnable_candidates",
        "candidate_order_policy": candidate_order_policy or "projection_order",
        "runnable_count": len(runnable),
        "runnable_candidates": runnable,
        "blocked_candidates": blocked,
        "blocked_missing": _unique_candidate_values(blocked, "missing_capabilities"),
        "owner_missing": _binding_capabilities(resolution_bindings, owner="user"),
        "repair_missing": repair_missing,
        "unsupported_missing": _binding_capabilities(
            resolution_bindings,
            owner="capability_gate",
        ),
        "resolution_bindings": resolution_bindings,
        "repair_candidate_count": sum(
            1 for item in runnable if item.get("capability_repair_mode") is True
        ),
        "reason": "capability gate projected runnable candidate set; agent chooses the actual todo",
        "owner_action": _owner_capability_action(resolution_bindings),
    }


def _build_blocked_capability_gate(
    *,
    source: str,
    available: list[str],
    blocked: list[dict[str, Any]],
) -> dict[str, Any]:
    missing = _unique_candidate_values(blocked, "missing_capabilities")
    resolution = _capability_resolution(missing)
    resolution_bindings = _blocked_capability_resolution_bindings(blocked)
    return {
        "schema_version": CAPABILITY_GATE_SCHEMA_VERSION,
        "source": source,
        "required": _unique_candidate_values(blocked, "required_capabilities"),
        "available": available,
        "missing": missing,
        "action": str(resolution["action"]),
        "decision_owner": resolution["decision_owner"],
        "owner_missing": list(resolution["owner_missing"]),
        "repair_missing": list(resolution["repair_missing"]),
        "unsupported_missing": resolution["unsupported_missing"],
        "resolution_steps": resolution["resolution_steps"],
        "resolution_bindings": resolution_bindings,
        "selection_policy": "no_runnable_candidate",
        "runnable_count": 0,
        "runnable_candidates": [],
        "blocked_candidates": blocked,
        "blocks_delivery": True,
        "reason": "all visible executable todo candidates require unavailable capabilities",
        "owner_action": _owner_capability_action(resolution_bindings),
    }


def build_capability_gate(
    agent_todo_summary: dict[str, Any] | None,
    *,
    available_capabilities: list[str],
    agent_identity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    candidates, source = _collect_capability_gate_candidates(agent_todo_summary)
    if not candidates:
        return None

    available = available_capabilities_with_defaults(available_capabilities)
    blocked, runnable, saw_requirement = _match_capability_candidates(
        candidates,
        available_capabilities=available,
    )
    if not saw_requirement and not blocked:
        return None
    if runnable:
        return _build_runnable_capability_gate(
            source=source,
            available=available,
            blocked=blocked,
            runnable=runnable,
            agent_identity=agent_identity,
        )
    return _build_blocked_capability_gate(
        source=source,
        available=available,
        blocked=blocked,
    )
