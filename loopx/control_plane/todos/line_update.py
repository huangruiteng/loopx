from __future__ import annotations

from typing import Any

from .active_state_editing import (
    TODO_SECTION_HEADINGS,
    find_todo_block,
    set_todo_marker,
    set_todo_text,
    todo_metadata_would_change,
)
from .contract import (
    TODO_MONITOR_METADATA_FIELDS,
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    TodoContinuationPolicy,
    metadata_line_for_todo_block,
    normalize_explore_result_node_refs,
    normalize_required_capabilities,
    normalize_removed_todo_continuation_policy,
    normalize_target_capabilities,
    normalize_todo_blocks_agent,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_continuation_policy,
    normalize_todo_decision_scope,
    normalize_todo_decision_scope_outcomes,
    normalize_todo_excluded_agents,
    normalize_todo_global_gate,
    normalize_todo_goal_bound,
    normalize_todo_id,
    normalize_todo_id_list,
    normalize_todo_no_followup,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_repository,
    parse_todo_metadata_line,
    require_supported_todo_resume_when,
)


def upsert_todo_metadata(
    lines: list[str], block: dict[str, Any], metadata_line: str | None
) -> bool:
    if not metadata_line:
        return False
    start = int(block["start"])
    end = int(block["end"])
    for index in range(start + 1, end):
        if parse_todo_metadata_line(lines[index]) is not None:
            if lines[index] == metadata_line:
                return False
            lines[index] = metadata_line
            return True
    insert_at = end
    while insert_at > start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, metadata_line)
    return True


def apply_todo_update_to_lines(
    lines: list[str],
    *,
    todo_id: str,
    text: str | None = None,
    status: str | None = None,
    role: str | None = None,
    note: str | None = None,
    evidence: str | None = None,
    reason: str | None = None,
    task_class: str | None = None,
    action_kind: str | None = None,
    task_repository: str | None = None,
    continuation_policy: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    explore_result_node_refs: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    decision_outcome: str | None = None,
    decision_scope_outcomes: Any = None,
    claimed_by: str | None = None,
    bound_agent: str | None = None,
    goal_bound: bool | None = None,
    clear_user_binding: bool = False,
    blocks_agent: str | None = None,
    clear_blocks_agent: bool = False,
    excluded_agents: list[str] | None = None,
    global_gate: bool | None = None,
    clear_global_gate: bool = False,
    unblocks_todo_id: str | None = None,
    successor_todo_ids: list[str] | None = None,
    resume_when: str | None = None,
    clear_resume_when: bool = False,
    no_followup: bool | None = None,
    monitor_metadata: dict[str, Any] | None = None,
    clear_claim: bool = False,
    claim_only: bool = False,
    updated_at: str,
) -> dict[str, Any]:
    normalized_resume_when = require_supported_todo_resume_when(resume_when)
    if normalized_resume_when and clear_resume_when:
        raise ValueError(
            "todo update accepts either resume_when or clear_resume_when, not both"
        )
    normalized_todo_id = normalize_todo_id(todo_id)
    if not normalized_todo_id:
        raise ValueError(
            "todo_id must use the public token shape "
            "todo_<letters-digits-underscore-hyphen>"
        )
    if role is not None and role not in TODO_SECTION_HEADINGS:
        raise ValueError("todo role must be one of: user, agent")
    block_match = find_todo_block(lines, todo_id=normalized_todo_id, role=role)
    if not block_match:
        raise ValueError(
            f"todo_id {normalized_todo_id!r} was not found in active user or agent todos"
        )
    resolved_role, section, _start, _end, block = block_match
    removed_continuation_policy = normalize_removed_todo_continuation_policy(
        block.get("removed_continuation_policy")
    )
    if removed_continuation_policy:
        if claim_only:
            raise ValueError(
                f"todo_id {normalized_todo_id!r} uses removed continuation_policy="
                f"{removed_continuation_policy}; repair it before claiming"
            )
        repair_policy = normalize_todo_continuation_policy(continuation_policy)
        repair_exclusions = normalize_todo_excluded_agents(excluded_agents)
        if (
            repair_policy != TodoContinuationPolicy.INDEPENDENT_HANDOFF.value
            or not repair_exclusions
        ):
            raise ValueError(
                f"todo_id {normalized_todo_id!r} uses removed continuation_policy="
                f"{removed_continuation_policy}; repair it explicitly with "
                "continuation_policy=independent_handoff and excluded_agents=<author>"
            )
    normalized_status = normalize_todo_status(status) if status else None
    if status and not normalized_status:
        raise ValueError("todo status must be one of: open, done, blocked, deferred")
    target_status = normalized_status or str(block.get("status") or TODO_STATUS_OPEN)
    if target_status == "deferred" and clear_resume_when:
        raise ValueError("cannot clear resume_when while todo status remains deferred")
    if claim_only and target_status != TODO_STATUS_OPEN:
        raise ValueError(
            f"todo claim requires status=open; todo_id {normalized_todo_id!r} "
            f"is status={target_status!r}"
        )
    status_changed = (
        set_todo_marker(lines, block, normalized_status) if normalized_status else False
    )
    text_changed = (
        set_todo_text(lines, block, text, status=target_status)
        if text is not None
        else False
    )

    updates: dict[str, Any] = {
        "todo_id": normalized_todo_id,
        "status": target_status,
    }
    if normalized_status == TODO_STATUS_DONE and not block.get("completed_at"):
        updates["completed_at"] = updated_at
    elif normalized_status and normalized_status != TODO_STATUS_DONE:
        updates["completed_at"] = None
    for key, value in (
        ("note", note),
        ("evidence", evidence),
        ("reason", reason),
        ("task_class", task_class),
        ("action_kind", action_kind),
        ("task_repository", task_repository),
        ("continuation_policy", continuation_policy),
    ):
        if value:
            updates[key] = value
    for key, value in (
        ("required_write_scopes", required_write_scopes),
        ("required_capabilities", required_capabilities),
        ("target_capabilities", target_capabilities),
        ("explore_result_node_refs", explore_result_node_refs),
        ("decision_scope", decision_scope),
        ("required_decision_scopes", required_decision_scopes),
        ("decision_outcome", decision_outcome),
        ("decision_scope_outcomes", decision_scope_outcomes),
    ):
        if value is not None:
            updates[key] = value
    if clear_claim:
        updates["claimed_by"] = None
    elif claimed_by:
        existing_claim = normalize_todo_claimed_by(block.get("claimed_by"))
        if claim_only and existing_claim and existing_claim != claimed_by:
            raise ValueError(
                f"todo_id {normalized_todo_id!r} is already claimed_by="
                f"{existing_claim!r}; clear or transfer the claim explicitly before "
                "claiming it"
            )
        updates["claimed_by"] = claimed_by
    if clear_user_binding:
        updates["bound_agent"] = None
        updates["goal_bound"] = None
    elif bound_agent:
        updates["bound_agent"] = bound_agent
        updates["goal_bound"] = None
    elif goal_bound is not None:
        updates["bound_agent"] = None
        updates["goal_bound"] = goal_bound
    if blocks_agent:
        updates["blocks_agent"] = blocks_agent
    elif clear_blocks_agent:
        updates["blocks_agent"] = None
    if excluded_agents is not None:
        updates["excluded_agents"] = excluded_agents
    if clear_global_gate:
        updates["global_gate"] = None
    elif global_gate is not None:
        updates["global_gate"] = global_gate
    if unblocks_todo_id:
        updates["unblocks_todo_id"] = unblocks_todo_id
    if successor_todo_ids is not None:
        updates["successor_todo_ids"] = successor_todo_ids
    if clear_resume_when:
        updates["resume_when"] = None
    elif normalized_resume_when:
        updates["resume_when"] = normalized_resume_when
    if no_followup is not None:
        updates["no_followup"] = no_followup
    for key, value in (monitor_metadata or {}).items():
        if key in TODO_MONITOR_METADATA_FIELDS:
            updates[key] = value
    metadata_line = metadata_line_for_todo_block(block, updates)
    semantic_metadata_changed = todo_metadata_would_change(lines, block, metadata_line)
    if status_changed or text_changed or semantic_metadata_changed:
        updates["updated_at"] = updated_at
        metadata_line = metadata_line_for_todo_block(block, updates)
    metadata_updated = upsert_todo_metadata(lines, block, metadata_line)
    effective_metadata = parse_todo_metadata_line(metadata_line or "") or {}
    return {
        "role": resolved_role,
        "section": section,
        "todo": block.get("text"),
        "todo_id": normalized_todo_id,
        "status": target_status,
        "status_changed": status_changed,
        "text_changed": text_changed,
        "metadata_updated": metadata_updated,
        "changed": status_changed or text_changed or metadata_updated,
        "claimed_by": normalize_todo_claimed_by(effective_metadata.get("claimed_by")),
        "bound_agent": normalize_todo_bound_agent(
            effective_metadata.get("bound_agent")
        ),
        "goal_bound": normalize_todo_goal_bound(effective_metadata.get("goal_bound")),
        "task_class": effective_metadata.get("task_class"),
        "action_kind": effective_metadata.get("action_kind"),
        "task_repository": normalize_todo_task_repository(
            effective_metadata.get("task_repository")
        ),
        "continuation_policy": normalize_todo_continuation_policy(
            effective_metadata.get("continuation_policy")
        ),
        "required_capabilities": normalize_required_capabilities(
            effective_metadata.get("required_capabilities")
        ),
        "target_capabilities": normalize_target_capabilities(
            effective_metadata.get("target_capabilities")
        ),
        "explore_result_node_refs": normalize_explore_result_node_refs(
            effective_metadata.get("explore_result_node_refs")
        ),
        "decision_scope": normalize_todo_decision_scope(
            effective_metadata.get("decision_scope")
        ),
        "required_decision_scopes": normalize_todo_required_decision_scopes(
            effective_metadata.get("required_decision_scopes")
        ),
        "decision_outcome": effective_metadata.get("decision_outcome"),
        "decision_scope_outcomes": normalize_todo_decision_scope_outcomes(
            effective_metadata.get("decision_scope_outcomes")
        ),
        "blocks_agent": normalize_todo_blocks_agent(
            effective_metadata.get("blocks_agent")
        ),
        "excluded_agents": normalize_todo_excluded_agents(
            effective_metadata.get("excluded_agents")
        ),
        "global_gate": normalize_todo_global_gate(
            effective_metadata.get("global_gate")
        ),
        "unblocks_todo_id": normalize_todo_id(
            effective_metadata.get("unblocks_todo_id")
        ),
        "successor_todo_ids": normalize_todo_id_list(
            effective_metadata.get("successor_todo_ids")
        ),
        "resume_when": normalize_todo_resume_when(
            effective_metadata.get("resume_when")
        ),
        "no_followup": normalize_todo_no_followup(
            effective_metadata.get("no_followup")
        ),
        "target_key": effective_metadata.get("target_key"),
        "cadence": effective_metadata.get("cadence"),
        "next_due_at": effective_metadata.get("next_due_at"),
        "expires_at": effective_metadata.get("expires_at"),
    }
