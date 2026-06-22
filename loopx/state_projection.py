from __future__ import annotations

import re
from typing import Any

from .todo_contract import TODO_TASK_PATTERN, todo_done_for_status, todo_status_from_marker


STATE_PROJECTION_GAP_SCHEMA_VERSION = "state_projection_gap_v0"
NEXT_ACTION_PROJECTION_WARNING_SCHEMA_VERSION = "next_action_projection_warning_v0"

SECTION_HEADING_PATTERN = re.compile(r"^##+\s+(.+?)\s*$")
BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$")
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
