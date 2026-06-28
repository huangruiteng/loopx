from __future__ import annotations

import re
from typing import Any

from .todo_contract import (
    TODO_TASK_PATTERN,
    build_todo_id,
    compact_todo_text,
    normalize_required_capabilities,
    normalize_required_write_scopes,
    normalize_target_capabilities,
    normalize_todo_decision_scope,
    normalize_todo_action_kind,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_global_gate,
    normalize_todo_id,
    normalize_todo_no_followup,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_class,
    parse_todo_metadata_line,
    todo_done_for_status,
    todo_status_from_marker,
)


STATE_PROJECTION_GAP_SCHEMA_VERSION = "state_projection_gap_v0"
NEXT_ACTION_PROJECTION_WARNING_SCHEMA_VERSION = "next_action_projection_warning_v0"
ACTIVE_STATE_STRUCTURED_PROJECTION_SCHEMA_VERSION = "active_state_structured_projection_v0"
ACTIVE_STATE_PROJECTION_DIAGNOSTICS_SCHEMA_VERSION = "active_state_projection_diagnostics_v0"
TODO_ITEM_SCHEMA_VERSION = "todo_item_v0"

SECTION_HEADING_PATTERN = re.compile(r"^##+\s+(.+?)\s*$")
BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$")
PRIORITY_PATTERN = re.compile(r"^\[(P[0-4])\]\s+(.+)$", re.IGNORECASE)
USER_TODO_HEADER_MARKERS = (
    "user todo",
    "owner review",
    "owner todo",
    "user action",
    "用户",
    "人工",
    "owner",
)
AGENT_TODO_HEADER_MARKERS = (
    "agent todo",
    "agent backlog",
    "agent action",
    "项目 agent",
    "agent 待办",
)
NEXT_ACTION_EXECUTABLE_PATTERN = re.compile(
    r"(?i)\b(?:run|repair|fix|implement|add|update|write|record|validate|"
    r"rerun|debug|inspect|analy[sz]e|sync|refresh|test|benchmark|trace|"
    r"replan|expand|split|todo)\b|"
    r"(?:推进|修复|实现|更新|写入|记录|验证|重跑|调试|检查|分析|审计|扩展|"
    r"拆分|补全|规划|待办)"
)
NEXT_ACTION_USER_WAIT_PATTERN = re.compile(
    r"(?i)\b(?:wait(?:ing)? for|await(?:ing)?|blocked by|gated by|"
    r"need(?:s|ed)?|requires?|request(?:s|ed)?|ask(?:ing)? for|pending)"
    r"\b.{0,120}\b(?:owner|user|operator|controller|human|approval|approve|"
    r"decision|gate|permission|choice)\b|"
    r"\b(?:owner|user|operator|controller|human)\s+"
    r"(?:gate|todo|action|decision|approval|permission|choice)\b|"
    r"\b(?:approval|permission)\s+(?:required|needed|pending)\b|"
    r"(?:等待|需要|受阻于|被.{0,20}阻塞).{0,80}"
    r"(?:用户|人工|决策|审批|批准|确认|owner)|"
    r"需(?:用户|人工|owner).{0,40}(?:决策|审批|批准|确认)|"
    r"需(?:决策|审批|批准|确认)|"
    r"请(?:用户|人工|owner).{0,40}(?:决策|审批|批准|确认)|"
    r"请(?:确认|审批|批准)|"
    r"待(?:用户|人工|owner)?(?:决策|审批|批准|确认)"
)
TODO_METADATA_KEYS = (
    "action_kind",
    "required_write_scopes",
    "required_capabilities",
    "target_capabilities",
    "decision_scope",
    "required_decision_scopes",
    "claimed_by",
    "blocks_agent",
    "global_gate",
    "unblocks_todo_id",
    "resume_when",
    "no_followup",
    "target_key",
    "cadence",
    "next_due_at",
    "last_checked_at",
    "result_hash",
    "consecutive_no_change",
    "material_change",
    "max_no_change_before_replan",
    "note",
    "evidence",
    "reason",
    "completed_at",
    "updated_at",
    "superseded_by",
)


def _compact_text(value: Any, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _action_projection_text(value: Any, *, limit: int = 320) -> str:
    return _compact_text(value, limit=limit)


def _action_projection_compare_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _action_projection_prefix(value: Any) -> str:
    text = _action_projection_compare_text(value)
    return text[:96]


def actions_are_projection_aligned(left: Any, right: Any) -> bool:
    left_text = _action_projection_compare_text(left)
    right_text = _action_projection_compare_text(right)
    if not left_text or not right_text:
        return False
    if left_text == right_text:
        return True
    left_prefix = _action_projection_prefix(left_text)
    right_prefix = _action_projection_prefix(right_text)
    for prefix, text in ((left_prefix, right_text), (right_prefix, left_text)):
        if prefix and len(prefix) >= 24 and prefix in text:
            return True
    shorter, longer = sorted((left_text, right_text), key=len)
    return len(shorter) >= 32 and shorter in longer


def next_action_projection_warning(
    *,
    active_state_next_action: Any,
    latest_run_recommended_action: Any,
    agent_lane_next_action: Any = None,
) -> dict[str, Any] | None:
    active_text = _action_projection_text(active_state_next_action)
    latest_text = _action_projection_text(latest_run_recommended_action)
    if not active_text or not latest_text:
        return None
    if actions_are_projection_aligned(active_text, latest_text):
        return None
    warning: dict[str, Any] = {
        "schema_version": NEXT_ACTION_PROJECTION_WARNING_SCHEMA_VERSION,
        "kind": "next_action_projection_mismatch",
        "severity": "warning",
        "requires_state_writeback": True,
        "active_state_next_action": active_text,
        "latest_run_recommended_action": latest_text,
        "reason": (
            "latest run recommended_action differs from the durable active-state "
            "Next Action"
        ),
        "recommended_action": (
            "if the latest run action is the intended durable route, write it back "
            "explicitly with refresh-state --next-action; otherwise keep treating "
            "the run recommendation and active-state Next Action as separate signals"
        ),
    }
    lane_text = _action_projection_text(agent_lane_next_action)
    if lane_text:
        warning["agent_lane_next_action"] = lane_text
    return warning


def is_user_wait_text(value: Any) -> bool:
    return bool(NEXT_ACTION_USER_WAIT_PATTERN.search(str(value or "")))


def _role_for_heading(heading: str) -> str | None:
    normalized = heading.strip().lower()
    if any(marker in normalized for marker in USER_TODO_HEADER_MARKERS):
        return "user"
    if any(marker in normalized for marker in AGENT_TODO_HEADER_MARKERS):
        return "agent"
    return None


def _open_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    value = summary.get("open_count")
    if value is None:
        value = summary.get("open")
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _section_lines(state_text: str, heading: str) -> list[str]:
    current = False
    lines: list[str] = []
    for line in state_text.splitlines():
        match = SECTION_HEADING_PATTERN.match(line)
        if match:
            if current:
                break
            current = match.group(1).strip().lower() == heading.lower()
            continue
        if current:
            lines.append(line)
    return lines


def _section_entries(lines: list[str]) -> list[str]:
    entries: list[str] = []
    current: list[str] = []
    for line in lines:
        bullet = BULLET_PATTERN.match(line)
        if bullet:
            if current:
                entries.append(_compact_text(" ".join(current)))
            current = [bullet.group(1)]
            continue
        if current and line.startswith((" ", "\t")):
            continuation = line.strip()
            if continuation:
                current.append(continuation)
            continue
        if current:
            entries.append(_compact_text(" ".join(current)))
            current = []
        stripped = line.strip()
        if stripped:
            entries.append(_compact_text(stripped))
    if current:
        entries.append(_compact_text(" ".join(current)))
    return [entry for entry in entries if entry]


def active_state_next_action_entries(
    state_text: str,
    *,
    limit: int | None = 3,
) -> list[str]:
    entries = _section_entries(_section_lines(state_text, "Next Action"))
    if limit is None:
        return entries
    return entries[: max(0, limit)]


def summarize_state_todo_open_counts(state_text: str) -> dict[str, int]:
    role: str | None = None
    counts = {"user": 0, "agent": 0}
    for line in state_text.splitlines():
        heading = SECTION_HEADING_PATTERN.match(line)
        if heading:
            role = _role_for_heading(heading.group(1))
            continue
        if role is None:
            continue
        match = TODO_TASK_PATTERN.match(line)
        if not match:
            continue
        marker, _text = match.groups()
        if not todo_done_for_status(todo_status_from_marker(marker)):
            counts[role] += 1
    return counts


def _active_state_compact_text(value: Any, *, limit: int = 500) -> str:
    text = compact_todo_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_active_state_frontmatter(state_text: str) -> dict[str, str]:
    if not state_text.startswith("---"):
        return {}
    parts = state_text.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key:
            result[key] = value.strip().strip('"')
    return result


def _todo_priority_parts(text: str) -> tuple[str | None, str]:
    match = PRIORITY_PATTERN.match(text)
    if not match:
        return None, text
    return match.group(1).upper(), _active_state_compact_text(match.group(2))


def _normalize_structured_todo_item(
    item: dict[str, Any],
    *,
    role: str,
    source_section: str,
) -> dict[str, Any]:
    text = _active_state_compact_text(item.get("text"))
    marker_status = todo_status_from_marker(item.get("marker"))
    metadata_status = normalize_todo_status(item.get("status"))
    status = metadata_status or marker_status
    todo_id = normalize_todo_id(item.get("todo_id"))
    todo_id_source = "metadata" if todo_id else "generated"
    todo_id = todo_id or build_todo_id(
        role=role,
        source_section=source_section,
        index=item.get("index"),
        text=text,
    )
    priority, title = _todo_priority_parts(text)
    action_kind = normalize_todo_action_kind(item.get("action_kind"))
    normalized: dict[str, Any] = {
        "schema_version": TODO_ITEM_SCHEMA_VERSION,
        "todo_id": todo_id,
        "todo_id_source": todo_id_source,
        "role": role,
        "source_section": source_section,
        "index": item.get("index"),
        "status": status,
        "done": todo_done_for_status(status),
        "text": text,
        "task_class": normalize_todo_task_class(
            item.get("task_class"),
            text=text,
            action_kind=action_kind,
        ),
    }
    if priority:
        normalized["priority"] = priority
        normalized["title"] = title
    if action_kind:
        normalized["action_kind"] = action_kind

    write_scopes = normalize_required_write_scopes(item.get("required_write_scopes"))
    if write_scopes:
        normalized["required_write_scopes"] = write_scopes
    required_capabilities = normalize_required_capabilities(item.get("required_capabilities"))
    if required_capabilities:
        normalized["required_capabilities"] = required_capabilities
    target_capabilities = normalize_target_capabilities(item.get("target_capabilities"))
    if target_capabilities:
        normalized["target_capabilities"] = target_capabilities
    decision_scope = normalize_todo_decision_scope(item.get("decision_scope"))
    if decision_scope:
        normalized["decision_scope"] = decision_scope
    required_decision_scopes = normalize_todo_required_decision_scopes(
        item.get("required_decision_scopes")
    )
    if required_decision_scopes:
        normalized["required_decision_scopes"] = required_decision_scopes
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    if claimed_by:
        normalized["claimed_by"] = claimed_by
    blocks_agent = normalize_todo_blocks_agent(item.get("blocks_agent"))
    if blocks_agent:
        normalized["blocks_agent"] = blocks_agent
    global_gate = normalize_todo_global_gate(item.get("global_gate"))
    if global_gate is not None:
        normalized["global_gate"] = global_gate
    unblocks_todo_id = normalize_todo_id(item.get("unblocks_todo_id"))
    if unblocks_todo_id:
        normalized["unblocks_todo_id"] = unblocks_todo_id
    resume_when = normalize_todo_resume_when(item.get("resume_when"))
    if resume_when:
        normalized["resume_when"] = resume_when
    no_followup = normalize_todo_no_followup(item.get("no_followup"))
    if no_followup is not None:
        normalized["no_followup"] = no_followup

    for key in TODO_METADATA_KEYS:
        if key in normalized or key not in item:
            continue
        value = item.get(key)
        if value not in (None, "", []):
            normalized[key] = value
    return normalized


def _parse_active_state_structured_todo_items(
    state_text: str,
) -> dict[str, list[dict[str, Any]]]:
    role: str | None = None
    source_sections: dict[str, str] = {}
    raw_items: dict[str, list[dict[str, Any]]] = {"user": [], "agent": []}
    current: dict[str, Any] | None = None

    for line in state_text.splitlines():
        heading = SECTION_HEADING_PATTERN.match(line)
        if heading:
            section = heading.group(1).strip()
            role = _role_for_heading(section)
            current = None
            if role and role not in source_sections:
                source_sections[role] = section
            continue
        if role is None:
            continue
        match = TODO_TASK_PATTERN.match(line)
        if match:
            marker, text = match.groups()
            current = {
                "index": len(raw_items[role]) + 1,
                "marker": marker,
                "text": _active_state_compact_text(text),
            }
            raw_items[role].append(current)
            continue
        if current is None or not line.startswith((" ", "\t")):
            continue
        metadata = parse_todo_metadata_line(line)
        if metadata:
            current.update(metadata)
            continue
        continuation = line.strip()
        if continuation:
            current["text"] = _active_state_compact_text(
                f"{current.get('text', '')} {continuation}"
            )

    result: dict[str, list[dict[str, Any]]] = {"user": [], "agent": []}
    for item_role, items in raw_items.items():
        source_section = source_sections.get(item_role) or f"{item_role.title()} Todo"
        result[item_role] = [
            _normalize_structured_todo_item(
                item,
                role=item_role,
                source_section=source_section,
            )
            for item in items
        ]
    return result


def _active_state_todo_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    open_items = [item for item in items if item.get("status") == "open"]
    done_items = [item for item in items if item.get("done") is True]
    implicit_items = [item for item in items if item.get("todo_id_source") == "generated"]
    return {
        "total_count": len(items),
        "open_count": len(open_items),
        "done_count": len(done_items),
        "implicit_todo_id_count": len(implicit_items),
        "items": items,
    }


def build_active_state_projection_diagnostics(
    *,
    frontmatter: dict[str, str],
    next_action_entries: list[str],
    todo_items: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    all_items = [item for items in todo_items.values() for item in items]
    if not frontmatter:
        warnings.append({"kind": "missing_frontmatter"})
    if not next_action_entries:
        warnings.append({"kind": "missing_next_action"})
    if not all_items:
        warnings.append({"kind": "missing_todo_sections"})
    implicit_items = [item for item in all_items if item.get("todo_id_source") == "generated"]
    if implicit_items:
        warnings.append(
            {
                "kind": "implicit_todo_ids",
                "count": len(implicit_items),
                "recommendation": (
                    "rewrite with loopx todo so every item carries explicit metadata"
                ),
            }
        )

    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for item in all_items:
        todo_id = str(item.get("todo_id") or "")
        seen[todo_id] = seen.get(todo_id, 0) + 1
        if seen[todo_id] == 2:
            duplicates.append(todo_id)
    if duplicates:
        errors.append({"kind": "duplicate_todo_ids", "todo_ids": duplicates})

    return {
        "schema_version": ACTIVE_STATE_PROJECTION_DIAGNOSTICS_SCHEMA_VERSION,
        "parseable": not errors,
        "migration_ready": bool(all_items) and not errors and not implicit_items,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def build_active_state_structured_projection(
    state_text: str,
    *,
    goal_id: str | None = None,
    source_ref: str = "ACTIVE_GOAL_STATE.md",
) -> dict[str, Any]:
    frontmatter = parse_active_state_frontmatter(state_text)
    next_entries = active_state_next_action_entries(state_text, limit=None)
    todo_items = _parse_active_state_structured_todo_items(state_text)
    diagnostics = build_active_state_projection_diagnostics(
        frontmatter=frontmatter,
        next_action_entries=next_entries,
        todo_items=todo_items,
    )
    projection: dict[str, Any] = {
        "schema_version": ACTIVE_STATE_STRUCTURED_PROJECTION_SCHEMA_VERSION,
        "source": "markdown_active_state",
        "source_ref": source_ref,
        "frontmatter": frontmatter,
        "next_action": {
            "count": len(next_entries),
            "first": next_entries[0] if next_entries else None,
            "entries": next_entries,
        },
        "todos": {
            "user": _active_state_todo_summary(todo_items["user"]),
            "agent": _active_state_todo_summary(todo_items["agent"]),
        },
        "diagnostics": diagnostics,
    }
    if goal_id:
        projection["goal_id"] = goal_id
    return projection


def state_projection_gap_warning(
    state_text: str,
    *,
    user_todos: dict[str, Any] | None = None,
    agent_todos: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    next_action_entries = _section_entries(_section_lines(state_text, "Next Action"))
    if not next_action_entries:
        return None

    fallback_counts = summarize_state_todo_open_counts(state_text)
    user_open = _open_count(user_todos)
    agent_open = _open_count(agent_todos)
    if user_todos is None:
        user_open = fallback_counts["user"]
    if agent_todos is None:
        agent_open = fallback_counts["agent"]

    evidence: list[dict[str, Any]] = []
    for entry in next_action_entries[:3]:
        executable = bool(NEXT_ACTION_EXECUTABLE_PATTERN.search(entry))
        waits_for_user = is_user_wait_text(entry)
        if agent_open == 0 and executable:
            evidence.append(
                {
                    "kind": "next_action_executable_without_agent_todo",
                    "target_role": "agent",
                    "section": "Next Action",
                    "text": entry,
                }
            )
        if user_open == 0 and waits_for_user:
            evidence.append(
                {
                    "kind": "next_action_waits_without_user_todo",
                    "target_role": "user",
                    "section": "Next Action",
                    "text": entry,
                }
            )

    if not evidence:
        return None

    target_roles = sorted(
        {
            str(item.get("target_role") or "")
            for item in evidence
            if item.get("target_role")
        }
    )
    return {
        "schema_version": STATE_PROJECTION_GAP_SCHEMA_VERSION,
        "kind": "state_projection_gap",
        "severity": "warning",
        "requires_todo_expansion": True,
        "agent_open_count": agent_open,
        "user_open_count": user_open,
        "target_roles": target_roles,
        "evidence_count": len(evidence),
        "first_evidence": evidence[:3],
        "recommended_action": (
            "Next Action 与 todo projection 不一致；先把可执行后续工作扩展为 "
            "Agent Todo，或把 owner/user gate 扩展为 User Todo，再继续 heartbeat delivery"
        ),
    }
