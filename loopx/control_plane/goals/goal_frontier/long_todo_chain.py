"""Edge-triggered long Todo-chain observations for goal-frontier replanning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...runtime.time import parse_timestamp
from ...todos.frontier_revision import (
    TODO_FRONTIER_REVISION_SCHEMA_VERSION,
    advancement_frontier_revision_from_index,
    selectable_advancement_frontier_revision,
)
from ...effect_runtime import effect_runtime_result
from ...todos.frontier_revision import frontier_source_facts


LONG_TODO_CHAIN_TRIGGER = "long_todo_chain"
TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
LONG_TODO_CHAIN_FRONTIER_REVISION_SCHEMA_VERSION = (
    TODO_FRONTIER_REVISION_SCHEMA_VERSION
)


@dataclass(frozen=True)
class LongTodoChainObservation:
    trigger_count: int
    count_kind: str
    selectable_open_count: int
    selectable_advancement_count: int
    current_agent_claimed_advancement_count: int
    unclaimed_advancement_count: int
    threshold: int
    agent_id: str | None
    frontier_revision: str | None
    frontier_revision_complete: bool

    def to_trigger(self) -> dict[str, Any]:
        trigger: dict[str, Any] = {
            "trigger_count": self.trigger_count,
            "count_kind": self.count_kind,
            "selectable_open_count": self.selectable_open_count,
            "selectable_advancement_count": self.selectable_advancement_count,
            "current_agent_claimed_advancement_count": (
                self.current_agent_claimed_advancement_count
            ),
            "unclaimed_advancement_count": self.unclaimed_advancement_count,
            "threshold": self.threshold,
            "agent_id": self.agent_id,
        }
        if self.frontier_revision_complete and self.frontier_revision:
            trigger["frontier_revision"] = self.frontier_revision
        return trigger


@dataclass(frozen=True)
class LongTodoChainAckDecision:
    acknowledged: bool
    rearmed_after_obligation_id: str | None = None


def long_todo_chain_source_checkpoint(
    source_items: list[dict[str, Any]],
    *,
    agent_id: str | None,
    frontier_revision_index: Any = None,
) -> tuple[dict[str, str], str] | None:
    """Return the revision and ordering fence for an exact Todo source."""

    projected = advancement_frontier_revision_from_index(
        frontier_revision_index,
        agent_id=agent_id,
    )
    frontier_revision, frontier_updated_at, revision_complete = (
        projected
        if projected is not None
        else selectable_advancement_frontier_revision(
            source_items,
            agent_id=agent_id,
        )
    )
    if not revision_complete or not frontier_revision or not frontier_updated_at:
        return None
    return (
        {
            "kind": LONG_TODO_CHAIN_TRIGGER,
            "frontier_revision": frontier_revision,
        },
        frontier_updated_at,
    )


def evaluate_long_todo_chain(
    *, agent_todo_summary: dict[str, Any] | None,
    agent_counts: dict[str, int], frontier_counts: dict[str, int],
    agent_id: str | None, agent_todo_source_items: list[dict[str, Any]] | None = None,
    latest_replan_ack: dict[str, Any] | None = None,
) -> tuple[LongTodoChainObservation | None, LongTodoChainAckDecision | None]:
    """One typed observation + checkpoint qualification, not two rule RPCs."""
    result = effect_runtime_result("goal.long_todo_chain.evaluate", {
        "schema_version": "long_todo_chain_request_v0", "operation": "observe",
        "summary": agent_todo_summary, "agent_counts": agent_counts,
        "frontier_counts": frontier_counts, "agent_id": agent_id,
        "rows": (
            None if isinstance((agent_todo_summary or {}).get("advancement_frontier_revision_index"), dict)
            else frontier_source_facts(agent_todo_source_items)
        ),
        "ack": latest_replan_ack,
    })
    observation = result["observation"]
    decision = result["decision"]
    return (
        LongTodoChainObservation(**observation) if observation is not None else None,
        LongTodoChainAckDecision(**decision) if decision is not None else None,
    )


def long_todo_chain_transition_is_fresh(
    *,
    frontier_updated_at: Any,
    transition_generated_at: Any,
) -> bool:
    """Fence a successor Todo against the authoritative source revision."""

    frontier_time = parse_timestamp(frontier_updated_at)
    transition_time = parse_timestamp(transition_generated_at)
    if frontier_time is None or transition_time is None:
        return False
    return bool(transition_time >= frontier_time)
