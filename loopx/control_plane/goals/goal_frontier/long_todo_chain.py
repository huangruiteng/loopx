"""Edge-triggered long Todo-chain observations for goal-frontier replanning."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from ...agents.agent_scope import agent_scope_item_claimed_by
from ...runtime.time import parse_timestamp
from ...todos.contract import normalize_todo_replan_obligation_id
from ...todos.projection import todo_item_task_class


LONG_TODO_CHAIN_TRIGGER = "long_todo_chain"
LONG_TODO_CHAIN_ADVANCEMENT_THRESHOLD = 15
LONG_TODO_CHAIN_OPEN_THRESHOLD = 20
TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
LONG_TODO_CHAIN_FRONTIER_REVISION_SCHEMA_VERSION = "todo_frontier_revision_v0"

_FRONTIER_REVISION_FIELDS = (
    "todo_id",
    "status",
    "done",
    "title",
    "text",
    "task_class",
    "claimed_by",
    "bound_agent",
    "blocks_agent",
    "excluded_agents",
    "priority",
    "action_kind",
    "task_domain",
    "task_repository",
    "capability_binding_ref",
    "required_capabilities",
    "target_capabilities",
    "target_key",
    "continuation_policy",
    "removed_continuation_policy",
    "decision_scope",
    "required_decision_scopes",
    "decision_outcome",
    "replan_obligation_id",
    "unblocks_todo_id",
    "depends_on_todo_id",
    "depends_on_todo_ids",
    "resume_when",
    "no_followup",
    "successor_todo_ids",
    "completion_continuation",
)


def _safe_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _selectable_advancement_frontier_revision(
    source_items: list[dict[str, Any]] | None,
    *,
    agent_id: str | None,
) -> tuple[str | None, str | None, bool]:
    """Return a complete material revision for one selectable agent lane.

    Terminal advancement rows remain relevant because completion and pruning
    mutate the frontier. Incomplete source revisions fail closed so a legacy
    projection cannot silently suppress an obligation.
    """

    if not isinstance(source_items, list):
        return None, None, False
    normalized_agent_id = str(agent_id or "").strip()
    revisions: list[dict[str, Any]] = []
    revision_times: list[tuple[Any, str]] = []
    relevant_count = 0
    for item in source_items:
        if not isinstance(item, dict):
            continue
        if todo_item_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        claimed_by = agent_scope_item_claimed_by(item)
        if normalized_agent_id and claimed_by not in {None, normalized_agent_id}:
            continue
        relevant_count += 1
        todo_id = str(item.get("todo_id") or "").strip()
        raw_revision = str(
            item.get("updated_at") or item.get("completed_at") or ""
        ).strip()
        parsed_revision = parse_timestamp(raw_revision)
        if not todo_id or parsed_revision is None:
            return None, None, False
        revisions.append(
            {
                field: item.get(field)
                for field in _FRONTIER_REVISION_FIELDS
                if item.get(field) is not None
            }
        )
        revision_times.append((parsed_revision, raw_revision))
    if relevant_count == 0 or not revisions:
        return None, None, False
    encoded = json.dumps(
        sorted(
            revisions,
            key=lambda item: str(item.get("todo_id") or ""),
        ),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return (
        f"{LONG_TODO_CHAIN_FRONTIER_REVISION_SCHEMA_VERSION}:"
        f"{sha256(encoded).hexdigest()[:24]}",
        max(revision_times, key=lambda item: item[0])[1],
        True,
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
    frontier_updated_at: str | None
    frontier_revision_complete: bool

    def to_trigger(self) -> dict[str, Any]:
        return {
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
            "frontier_revision": self.frontier_revision,
            "frontier_updated_at": self.frontier_updated_at,
            "frontier_revision_complete": self.frontier_revision_complete,
        }


@dataclass(frozen=True)
class LongTodoChainAckDecision:
    acknowledged: bool
    rearmed_after_obligation_id: str | None = None


def long_todo_chain_trigger_checkpoint_for_source(
    source_items: list[dict[str, Any]],
    *,
    agent_id: str | None,
) -> dict[str, str] | None:
    """Return the post-transition checkpoint for an exact Todo source."""

    frontier_revision, _, revision_complete = (
        _selectable_advancement_frontier_revision(source_items, agent_id=agent_id)
    )
    if not revision_complete or not frontier_revision:
        return None
    return {
        "kind": LONG_TODO_CHAIN_TRIGGER,
        "frontier_revision": frontier_revision,
    }


def observe_long_todo_chain(
    *,
    agent_todo_summary: dict[str, Any] | None,
    agent_counts: dict[str, int],
    frontier_counts: dict[str, int],
    agent_id: str | None,
    agent_todo_source_items: list[dict[str, Any]] | None = None,
) -> LongTodoChainObservation | None:
    """Observe one agent-scoped long chain without inferring from prose."""

    current_advancement = frontier_counts.get(
        "current_agent_claimed_advancement_count", 0
    )
    unclaimed_advancement = frontier_counts.get("unclaimed_advancement_count", 0)
    selectable_advancement = current_advancement + unclaimed_advancement
    if isinstance(agent_todo_summary, dict):
        current_open = _safe_non_negative_int(
            agent_todo_summary.get("current_agent_claimed_open_count")
        )
        unclaimed_open = _safe_non_negative_int(
            agent_todo_summary.get("unclaimed_open_count")
        )
        selectable_open = max(
            current_open + unclaimed_open,
            selectable_advancement,
        )
    else:
        selectable_open = max(agent_counts.get("open", 0), selectable_advancement)
    threshold: int | None = None
    trigger_count = 0
    count_kind = ""
    if selectable_advancement >= LONG_TODO_CHAIN_ADVANCEMENT_THRESHOLD:
        threshold = LONG_TODO_CHAIN_ADVANCEMENT_THRESHOLD
        trigger_count = selectable_advancement
        count_kind = "selectable_advancement_todos"
    elif (
        selectable_open >= LONG_TODO_CHAIN_OPEN_THRESHOLD
        and selectable_advancement > 0
    ):
        threshold = LONG_TODO_CHAIN_OPEN_THRESHOLD
        trigger_count = selectable_open
        count_kind = "selectable_open_todos"
    if threshold is None:
        return None
    frontier_revision, frontier_updated_at, revision_complete = (
        _selectable_advancement_frontier_revision(
            agent_todo_source_items,
            agent_id=agent_id,
        )
    )
    return LongTodoChainObservation(
        trigger_count=trigger_count,
        count_kind=count_kind,
        selectable_open_count=selectable_open,
        selectable_advancement_count=selectable_advancement,
        current_agent_claimed_advancement_count=current_advancement,
        unclaimed_advancement_count=unclaimed_advancement,
        threshold=threshold,
        agent_id=agent_id,
        frontier_revision=frontier_revision,
        frontier_updated_at=frontier_updated_at,
        frontier_revision_complete=revision_complete,
    )


def classify_long_todo_chain_ack(
    observation: LongTodoChainObservation,
    latest_replan_ack: dict[str, Any] | None,
) -> LongTodoChainAckDecision:
    """Classify an accepted checkpoint against the current frontier revision."""

    if (
        not isinstance(latest_replan_ack, dict)
        or latest_replan_ack.get("recorded") is not True
    ):
        return LongTodoChainAckDecision(acknowledged=False)
    semantic_delta_value = latest_replan_ack.get("semantic_delta")
    semantic_delta: dict[str, Any] = (
        semantic_delta_value if isinstance(semantic_delta_value, dict) else {}
    )
    trigger_kinds = {
        str(value or "").strip()
        for value in semantic_delta.get("trigger_kinds") or []
        if str(value or "").strip()
    }
    obligation_id = normalize_todo_replan_obligation_id(
        semantic_delta.get("obligation_id")
    )
    if (
        semantic_delta.get("accepted") is not True
        or LONG_TODO_CHAIN_TRIGGER not in trigger_kinds
        or not obligation_id
    ):
        return LongTodoChainAckDecision(acknowledged=False)
    if not observation.frontier_revision_complete or not observation.frontier_revision:
        return LongTodoChainAckDecision(acknowledged=False)
    checkpoint_matches = any(
        isinstance(checkpoint, dict)
        and str(checkpoint.get("kind") or "").strip() == LONG_TODO_CHAIN_TRIGGER
        and str(checkpoint.get("frontier_revision") or "").strip()
        == observation.frontier_revision
        for checkpoint in semantic_delta.get("trigger_checkpoints") or []
    )
    if checkpoint_matches:
        return LongTodoChainAckDecision(acknowledged=True)
    return LongTodoChainAckDecision(
        acknowledged=False,
        rearmed_after_obligation_id=obligation_id,
    )


def long_todo_chain_transition_is_fresh(
    obligation: dict[str, Any],
    *,
    transition_generated_at: Any,
) -> bool:
    """Fence a successor Todo that cannot yet persist trigger checkpoints."""

    long_chain_trigger = next(
        (
            trigger
            for trigger in obligation.get("triggers") or []
            if isinstance(trigger, dict)
            and trigger.get("kind") == LONG_TODO_CHAIN_TRIGGER
        ),
        None,
    )
    if long_chain_trigger is None:
        return True
    frontier_time = parse_timestamp(long_chain_trigger.get("frontier_updated_at"))
    transition_time = parse_timestamp(transition_generated_at)
    if frontier_time is None or transition_time is None:
        return False
    return bool(transition_time >= frontier_time)
