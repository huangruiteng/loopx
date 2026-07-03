from __future__ import annotations

from typing import Any, Callable, Optional


MAX_SUBAGENT_ACTIVITY_ITEMS = 5

PublicSafeText = Callable[..., Optional[str]]
PublicSafeList = Callable[..., list[str]]


def subagent_state(
    run: dict[str, Any],
    *,
    public_safe_compact_text: PublicSafeText,
) -> str | None:
    for field in ("result_status", "state", "status", "classification"):
        value = public_safe_compact_text(run.get(field), limit=80)
        if value:
            return value
    return None


def subagent_quota_spend(run: dict[str, Any]) -> int:
    for field in ("quota_spend", "quota_slots", "spent_slots"):
        raw = run.get(field)
        if isinstance(raw, bool):
            continue
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            pass
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    raw_slots = quota_event.get("slots")
    try:
        return max(0, int(raw_slots))
    except (TypeError, ValueError):
        return 0


def compact_subagent_run(
    raw: dict[str, Any],
    *,
    parent_goal_id: str | None = None,
    parent_run_id: str | None = None,
    public_safe_compact_text: PublicSafeText,
    public_safe_compact_list: PublicSafeList,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    run_id = public_safe_compact_text(
        raw.get("run_id") or raw.get("id") or raw.get("generated_at"),
        limit=120,
    )
    role = public_safe_compact_text(raw.get("agent_role") or raw.get("role"), limit=80)
    state = subagent_state(raw, public_safe_compact_text=public_safe_compact_text)
    if not (run_id or role or state):
        return None

    compact: dict[str, Any] = {}
    if run_id:
        compact["run_id"] = run_id
    goal_id = public_safe_compact_text(raw.get("goal_id") or raw.get("id"), limit=120)
    if goal_id:
        compact["goal_id"] = goal_id
    parent_run = public_safe_compact_text(raw.get("parent_run_id") or parent_run_id, limit=120)
    if parent_run:
        compact["parent_run_id"] = parent_run
    spawned_by = public_safe_compact_text(raw.get("spawned_by_goal_id") or parent_goal_id, limit=120)
    if spawned_by:
        compact["spawned_by_goal_id"] = spawned_by
    if role:
        compact["agent_role"] = role
    if state:
        compact["state"] = state
    for field in ("claim_id", "approval_state"):
        value = public_safe_compact_text(raw.get(field), limit=120)
        if value:
            compact[field] = value
    work_scope = public_safe_compact_list(raw.get("work_scope") or raw.get("scope"))
    if work_scope:
        compact["work_scope"] = work_scope
    touched_paths = public_safe_compact_list(raw.get("touched_paths") or raw.get("changed_files"))
    if touched_paths:
        compact["touched_paths"] = touched_paths
    raw_touched = raw.get("touched_paths") or raw.get("changed_files")
    if isinstance(raw_touched, list):
        compact["touched_path_count"] = len(raw_touched)
    handoff = public_safe_compact_text(raw.get("handoff_summary") or raw.get("summary"), limit=260)
    if handoff:
        compact["handoff_summary"] = handoff
    quota_spend = subagent_quota_spend(raw)
    if quota_spend:
        compact["quota_spend_slots"] = quota_spend
    return compact


def subagent_activity_for_goal(
    goal: dict[str, Any],
    *,
    public_safe_compact_text: PublicSafeText,
    public_safe_compact_list: PublicSafeList,
) -> dict[str, Any] | None:
    if not isinstance(goal, dict):
        return None
    parent_goal_id = str(goal.get("id") or "")
    latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
    children: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_child(raw: dict[str, Any], *, parent_run_id: str | None = None) -> None:
        child = compact_subagent_run(
            raw,
            parent_goal_id=parent_goal_id or None,
            parent_run_id=parent_run_id,
            public_safe_compact_text=public_safe_compact_text,
            public_safe_compact_list=public_safe_compact_list,
        )
        if not child:
            return
        key = (
            str(child.get("run_id") or ""),
            str(child.get("goal_id") or ""),
            str(child.get("agent_role") or ""),
        )
        if key in seen:
            return
        seen.add(key)
        children.append(child)

    for run in latest_runs:
        if not isinstance(run, dict):
            continue
        parent_run_id = str(run.get("run_id") or run.get("generated_at") or "")
        for child in run.get("subagents") or []:
            if isinstance(child, dict):
                add_child(child, parent_run_id=parent_run_id)
        if run.get("parent_run_id") or run.get("spawned_by_goal_id") or run.get("agent_role"):
            add_child(run, parent_run_id=str(run.get("parent_run_id") or ""))

    if not children:
        return None
    limited = children[:MAX_SUBAGENT_ACTIVITY_ITEMS]
    completed_states = {"completed", "done", "success", "passed"}
    active_states = {"running", "active", "in_progress", "queued", "started"}
    completed = sum(1 for child in children if str(child.get("state") or "").lower() in completed_states)
    active = sum(1 for child in children if str(child.get("state") or "").lower() in active_states)
    quota_spend = sum(int(child.get("quota_spend_slots") or 0) for child in children)
    return {
        "source": "run_history",
        "parent_goal_id": parent_goal_id,
        "child_count": len(children),
        "visible_child_count": len(limited),
        "completed_count": completed,
        "active_count": active,
        "quota_spend_slots": quota_spend,
        "items": limited,
        "proxy_note": "compact child-run projection only; parent controller remains the authority for locks, writes, and merge decisions",
    }
