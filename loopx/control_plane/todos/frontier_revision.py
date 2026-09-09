"""Compact, complete revisions for Todo advancement frontiers."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from ..runtime.time import parse_timestamp
from .contract import normalize_todo_claimed_by
from .projection import todo_item_task_class


TODO_FRONTIER_REVISION_SCHEMA_VERSION = "todo_frontier_revision_v0"
TODO_FRONTIER_REVISION_INDEX_SCHEMA_VERSION = "todo_frontier_revision_index_v0"
TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"

FRONTIER_REVISION_FIELDS = (
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


def _revision_for_claims(
    source_items: list[dict[str, Any]] | None,
    *,
    included_claims: set[str | None] | None,
) -> tuple[str | None, str | None, bool]:
    if not isinstance(source_items, list):
        return None, None, False
    revisions: list[dict[str, Any]] = []
    revision_times: list[tuple[Any, str]] = []
    relevant_count = 0
    for item in source_items:
        if not isinstance(item, dict):
            continue
        if todo_item_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if included_claims is not None and claimed_by not in included_claims:
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
                for field in FRONTIER_REVISION_FIELDS
                if item.get(field) is not None
            }
        )
        revision_times.append((parsed_revision, raw_revision))
    if relevant_count == 0 or not revisions:
        return None, None, False
    encoded = json.dumps(
        sorted(revisions, key=lambda item: str(item.get("todo_id") or "")),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return (
        f"{TODO_FRONTIER_REVISION_SCHEMA_VERSION}:"
        f"{sha256(encoded).hexdigest()[:24]}",
        max(revision_times, key=lambda item: item[0])[1],
        True,
    )


def selectable_advancement_frontier_revision(
    source_items: list[dict[str, Any]] | None,
    *,
    agent_id: str | None,
) -> tuple[str | None, str | None, bool]:
    """Return the material revision for one agent's selectable frontier."""

    normalized_agent_id = normalize_todo_claimed_by(agent_id)
    included_claims = (
        {None, normalized_agent_id} if normalized_agent_id else None
    )
    return _revision_for_claims(source_items, included_claims=included_claims)


def _checkpoint(
    source_items: list[dict[str, Any]],
    *,
    included_claims: set[str | None] | None,
) -> dict[str, Any]:
    revision, updated_at, complete = _revision_for_claims(
        source_items,
        included_claims=included_claims,
    )
    checkpoint: dict[str, Any] = {"complete": complete}
    if complete and revision and updated_at:
        checkpoint["frontier_revision"] = revision
        checkpoint["frontier_updated_at"] = updated_at
    return checkpoint


def build_advancement_frontier_revision_index(
    source_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project full frontier identity without retaining every Todo row."""

    agent_ids = sorted(
        {
            claimed_by
            for item in source_items
            if isinstance(item, dict)
            and todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
            and (claimed_by := normalize_todo_claimed_by(item.get("claimed_by")))
        }
    )
    return {
        "schema_version": TODO_FRONTIER_REVISION_INDEX_SCHEMA_VERSION,
        "all": _checkpoint(source_items, included_claims=None),
        "unclaimed": _checkpoint(source_items, included_claims={None}),
        "by_agent": [
            {
                "agent_id": agent_id,
                **_checkpoint(source_items, included_claims={None, agent_id}),
            }
            for agent_id in agent_ids
        ],
    }


def attach_advancement_frontier_revision_index(
    summary: dict[str, Any],
    source_items: list[dict[str, Any]],
    *,
    role: str | None,
) -> None:
    """Attach the complete decision checkpoint only to Agent Todo summaries."""

    if role == "agent":
        summary["advancement_frontier_revision_index"] = (
            build_advancement_frontier_revision_index(source_items)
        )


def advancement_frontier_revision_from_index(
    value: Any,
    *,
    agent_id: str | None,
) -> tuple[str | None, str | None, bool] | None:
    """Read one complete lane checkpoint; invalid indexes fail closed."""

    if not isinstance(value, dict):
        return None
    if value.get("schema_version") != TODO_FRONTIER_REVISION_INDEX_SCHEMA_VERSION:
        return None, None, False
    normalized_agent_id = normalize_todo_claimed_by(agent_id)
    checkpoint: Any = value.get("all")
    if normalized_agent_id:
        by_agent = value.get("by_agent")
        if not isinstance(by_agent, list):
            return None, None, False
        checkpoint = next(
            (
                row
                for row in by_agent
                if isinstance(row, dict)
                and normalize_todo_claimed_by(row.get("agent_id"))
                == normalized_agent_id
            ),
            value.get("unclaimed"),
        )
    if not isinstance(checkpoint, dict) or checkpoint.get("complete") is not True:
        return None, None, False
    revision = str(checkpoint.get("frontier_revision") or "").strip()
    updated_at = str(checkpoint.get("frontier_updated_at") or "").strip()
    if not revision or parse_timestamp(updated_at) is None:
        return None, None, False
    return revision, updated_at, True
