from __future__ import annotations

from typing import Any

from ..todos.todo_semantics import agent_scoped_selectable_advancement_todo_ids
from .goal_vision_read_model import (
    acceptance_gaps_from_agent_vision,
    latest_agent_vision_from_runs,
)
from .goal_vision_wait import build_goal_vision_wait_state


def attach_active_vision_waits(
    summary: dict[str, Any],
    runs: list[dict[str, Any]] | None,
    *,
    role: str | None,
    items: list[dict[str, Any]],
    lineage_items: list[dict[str, Any]] | None,
) -> None:
    """Derive bounded wait witnesses before the canonical Todo rows are sliced.

    The ordinary refresh-state/Turn vision and Todo lifecycles are the only
    producers. This read model is rebuilt on every source read, never persisted
    or authored separately. Only positive proofs cross the presentation seam.
    """
    if role != "agent" or not runs:
        return

    agent_ids = {
        str(
            (run.get("agent_vision") or {}).get("agent_id") or run.get("agent_id") or ""
        )
        for run in runs
        if isinstance(run, dict) and isinstance(run.get("agent_vision"), dict)
    } - {""}
    proofs = []
    for agent_id in sorted(agent_ids):
        vision = latest_agent_vision_from_runs(runs, goal_id="", agent_id=agent_id)
        gaps = acceptance_gaps_from_agent_vision(vision)
        wait = build_goal_vision_wait_state(
            agent_todo_summary=None,
            agent_id=agent_id,
            acceptance_gaps=gaps,
            selectable_advancement_count=len(
                agent_scoped_selectable_advancement_todo_ids(
                    {"executable_backlog_items": items},
                    agent_id=agent_id,
                )
            ),
            source_items=items,
            lineage_source_items=[*(lineage_items or []), *items],
        )
        if wait:
            proofs.append(wait)
    if proofs:
        summary["vision_wait_states"] = proofs
