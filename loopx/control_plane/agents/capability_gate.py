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
        capability for capability in missing if capability in CAPABILITY_OWNER_GATE_HINTS
    ]
    repair_missing = [
        capability for capability in missing if capability in CAPABILITY_REPAIR_BRIDGE_HINTS
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


def build_capability_gate(
    agent_todo_summary: dict[str, Any] | None,
    *,
    available_capabilities: list[str],
    agent_identity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    monitor_capability_blocked_due_items = agent_todo_summary.get(
        "monitor_capability_blocked_due_items"
    )
    blocked_monitor_items = (
        monitor_capability_blocked_due_items
        if isinstance(monitor_capability_blocked_due_items, list)
        else []
    )
    monitor_due_items_value = agent_todo_summary.get("monitor_due_items")
    runnable_monitor_items = (
        monitor_due_items_value if isinstance(monitor_due_items_value, list) else []
    )
    active_next_action_executable_items = agent_todo_summary.get(
        "active_next_action_executable_items"
    )
    executable_backlog_items = agent_todo_summary.get("executable_backlog_items")
    first_executable_items = agent_todo_summary.get("first_executable_items")
    if (
        isinstance(active_next_action_executable_items, list)
        and active_next_action_executable_items
    ):
        raw_items = [
            *active_next_action_executable_items,
            *(
                executable_backlog_items
                if isinstance(executable_backlog_items, list)
                else []
            ),
        ]
        source = "agent_todo_summary.active_next_action_executable_items"
    elif isinstance(executable_backlog_items, list) and executable_backlog_items:
        raw_items = executable_backlog_items
        source = "agent_todo_summary.executable_backlog_items"
    elif isinstance(first_executable_items, list) and first_executable_items:
        raw_items = first_executable_items
        source = "agent_todo_summary.first_executable_items"
    else:
        raw_items = []
        source = "agent_todo_summary.executable_backlog_items"
    monitor_sources: list[str] = []
    if runnable_monitor_items:
        monitor_sources.append("agent_todo_summary.monitor_due_items")
    if blocked_monitor_items:
        monitor_sources.append("agent_todo_summary.monitor_capability_blocked_due_items")
    if monitor_sources:
        has_advancement_items = bool(raw_items)
        raw_items = [*raw_items, *runnable_monitor_items, *blocked_monitor_items]
        source = (
            "+".join([source, *monitor_sources])
            if has_advancement_items
            else "+".join(monitor_sources)
        )
    deduped_raw_items: list[Any] = []
    seen_raw: set[tuple[str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            deduped_raw_items.append(item)
            continue
        identity = _capability_item_identity(item)
        if identity in seen_raw:
            continue
        seen_raw.add(identity)
        deduped_raw_items.append(item)
    raw_items = deduped_raw_items
    due_monitor_identities = {
        _capability_item_identity(item)
        for item in [*runnable_monitor_items, *blocked_monitor_items]
        if isinstance(item, dict)
    }
    candidates = [
        item
        for item in raw_items
        if isinstance(item, dict)
        and todo_item_is_actionable_open(item)
        and (
            todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
            or _capability_item_identity(item) in due_monitor_identities
        )
    ]
    if not candidates:
        return None

    available = available_capabilities_with_defaults(available_capabilities)
    blocked: list[dict[str, Any]] = []
    runnable: list[dict[str, Any]] = []
    saw_requirement = False
    for item in candidates:
        required = normalize_required_capabilities(item.get("required_capabilities"))
        targets = normalize_target_capabilities(item.get("target_capabilities"))
        if required or targets:
            saw_requirement = True
        missing = missing_required_capabilities(
            item,
            available_capabilities=available,
        )
        missing_targets = [
            capability for capability in targets if capability not in available
        ]
        if missing:
            blocked.append(_capability_candidate_item(item, missing=missing))
            continue
        runnable.append(
            _capability_candidate_item(
                item,
                missing=[],
                missing_target_capabilities=missing_targets,
            )
        )

    if not saw_requirement and not blocked:
        return None
    if runnable:
        runnable, candidate_order_policy = _sort_capability_runnable_candidates(
            runnable,
            agent_identity=agent_identity,
        )
        runnable_required: list[str] = []
        blocked_missing: list[str] = []
        repair_missing: list[str] = []
        for item in runnable:
            for capability in item.get("required_capabilities") or []:
                if capability not in runnable_required:
                    runnable_required.append(str(capability))
            if item.get("capability_repair_mode") is True:
                for capability in item.get("missing_target_capabilities") or []:
                    if capability not in repair_missing:
                        repair_missing.append(str(capability))
        for item in blocked:
            for capability in item.get("missing_capabilities") or []:
                if capability not in blocked_missing:
                    blocked_missing.append(str(capability))
        resolution_bindings = _blocked_capability_resolution_bindings(blocked)
        owner_missing = _binding_capabilities(resolution_bindings, owner="user")
        for capability in _binding_capabilities(resolution_bindings, owner="agent"):
            if capability not in repair_missing:
                repair_missing.append(capability)
        unsupported_missing = _binding_capabilities(
            resolution_bindings,
            owner="capability_gate",
        )
        return {
            "schema_version": CAPABILITY_GATE_SCHEMA_VERSION,
            "source": source,
            "required": runnable_required,
            "available": available,
            "missing": [],
            "action": "run",
            "decision_owner": "agent",
            "selection_policy": "agent_steering_audit_over_runnable_candidates",
            "candidate_order_policy": candidate_order_policy or "projection_order",
            "runnable_count": len(runnable),
            "runnable_candidates": runnable,
            "blocked_candidates": blocked,
            "blocked_missing": blocked_missing,
            "owner_missing": owner_missing,
            "repair_missing": repair_missing,
            "unsupported_missing": unsupported_missing,
            "resolution_bindings": resolution_bindings,
            "repair_candidate_count": sum(
                1 for item in runnable if item.get("capability_repair_mode") is True
            ),
            "reason": "capability gate projected runnable candidate set; agent chooses the actual todo",
            "owner_action": _owner_capability_action(resolution_bindings),
        }

    missing_all: list[str] = []
    required_all: list[str] = []
    for item in blocked:
        for capability in item.get("required_capabilities") or []:
            if capability not in required_all:
                required_all.append(str(capability))
        for capability in item.get("missing_capabilities") or []:
            if capability not in missing_all:
                missing_all.append(str(capability))
    resolution = _capability_resolution(missing_all)
    resolution_bindings = _blocked_capability_resolution_bindings(blocked)
    action = str(resolution["action"])
    owner_missing = list(resolution["owner_missing"])
    repair_missing = list(resolution["repair_missing"])
    return {
        "schema_version": CAPABILITY_GATE_SCHEMA_VERSION,
        "source": source,
        "required": required_all,
        "available": available,
        "missing": missing_all,
        "action": action,
        "decision_owner": resolution["decision_owner"],
        "owner_missing": owner_missing,
        "repair_missing": repair_missing,
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
