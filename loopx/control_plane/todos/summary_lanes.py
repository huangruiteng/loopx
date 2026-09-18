"""Legacy fact codec and ordinal readback for the typed summary lane owner."""
from __future__ import annotations

from typing import Any

from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from ..runtime.time import now_utc
from .contract import normalize_todo_resume_when, normalize_todo_watch_only
from .todo_semantics import (
    todo_item_expires_at, todo_item_next_due_at, todo_item_task_class,
    todo_presentation_sort_key,
)


def project_summary_lanes(items: list[dict[str, Any]], preferred_todo_ids: set[str] | None) -> dict[str, Any]:
    rows = []
    for item in items:
        resume = normalize_todo_resume_when(item.get("resume_when"))
        condition = item.get("resume_condition")
        evaluated = (isinstance(condition, dict)
            and condition.get("schema_version") == "todo_resume_condition_v0"
            and condition.get("resume_when") == resume
            and isinstance(condition.get("satisfied"), bool)
            and item.get("resume_ready") is condition.get("satisfied"))
        due = todo_item_next_due_at(item)
        expires = todo_item_expires_at(item)
        guard = item.get("goal_acceptance_guard")
        rows.append({"status": item.get("status") or ("done" if item.get("done") else "open"),
            "done": bool(item.get("done")), "task_class": todo_item_task_class(item),
            "has_resume": bool(resume), "resume_ready": item.get("resume_ready"),
            "resume_evaluated": evaluated, "acceptance_blocked": isinstance(guard, dict) and guard.get("allowed") is False,
            "claimed": bool(item.get("claimed_by")), "preferred": item.get("todo_id") in (preferred_todo_ids or set()),
            "watch_only": normalize_todo_watch_only(item.get("watch_only")) is True,
            "due_at": due.timestamp() if due else None, "expires_at": expires.timestamp() if expires else None,
            "sort": list(todo_presentation_sort_key(item))})
    try:
        result = effect_runtime_result("todo.summary_lanes.project", {
            "schema_version": "todo_summary_lanes_request_v0", "rows": rows, "observed_at": now_utc().timestamp(),
        })
    except EffectRuntimeRejected as error:
        raise ValueError(str(error)) from error
    if not isinstance(result, dict) or result.get("schema_version") != "todo_summary_lanes_v0":
        raise ValueError("invalid typed Todo summary lanes")
    lanes = result["lanes"]
    if not isinstance(lanes, dict) or any(
        not isinstance(indices, list) or any(type(index) is not int or not 0 <= index < len(items) for index in indices)
        for indices in lanes.values()
    ):
        raise ValueError("invalid Todo summary source ordinal")
    return {"lanes": {key: [items[index] for index in indices] for key, indices in lanes.items()},
            "work_counts": result["work_counts"]}
