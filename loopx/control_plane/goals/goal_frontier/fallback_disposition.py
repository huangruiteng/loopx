from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...todos.contract import (
    normalize_todo_id,
)
from ...todos.deferred_resume import todo_summary_blocked_successor_items
from ...todos.projection import (
    agent_scoped_selectable_advancement_todo_ids,
)
from ..goal_vision_state import goal_vision_state_is_closed

# Single owner of the vision todo_delta action contract shared by the
# acceptance-gap projection and this module.
VISION_FRONTIER_TODO_DELTA_ACTIONS = frozenset(
    {"activate", "create", "reopen", "resume", "retain"}
)
# create/reopen entries are bounded successor declarations and resolve the
# fallback disposition on their own; activate/resume/retain entries only link
# the vision to existing Todos and still need a selectable frontier match.
VISION_TODO_DELTA_SUCCESSOR_ACTIONS = frozenset({"create", "reopen"})
VISION_TODO_DELTA_LINKAGE_ACTIONS = frozenset(
    VISION_FRONTIER_TODO_DELTA_ACTIONS - VISION_TODO_DELTA_SUCCESSOR_ACTIONS
)
VISION_TODO_DELTA_ID_LIMIT = 120
VISION_FALLBACK_DECLARATION_ENTRY_LIMIT = 4
VISION_FALLBACK_DECLARATION_FIELDS = ("target_todo_id", "successor_todo_id")
VISION_FALLBACK_GAP_TRIGGER = "vision_fallback_unresolved"
VISION_FALLBACK_GAP_REASON_CODE = "declared_fallback_without_runnable_or_terminal"
VISION_FALLBACK_TERMINAL_PATH_OUTCOME = "stop"
VISION_FALLBACK_RUNNABLE_ITEM_LIMIT = 3
VISION_FALLBACK_RECOMMENDED_ACTION = (
    "resolve the declared fallback direction: link or retain a runnable "
    "successor Todo referencing it, declare a bounded create/reopen "
    "successor, or record an explicit terminal no-follow-up disposition; "
    "do not invent a user gate"
)


@dataclass(frozen=True)
class FallbackDeclaration:
    """Structured declaration of a fallback direction and its associated work."""

    declaration_id: str
    target_todo_id: str | None = None
    successor_todo_id: str | None = None

    @property
    def candidate_todo_ids(self) -> set[str]:
        return {
            todo_id
            for todo_id in (
                self.target_todo_id,
                self.successor_todo_id,
                self.declaration_id,
            )
            if todo_id
        }

    @property
    def unresolved_todo_id(self) -> str:
        return self.target_todo_id or self.declaration_id


def _compact_text(value: Any, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def parse_vision_todo_delta_entries(entries: Any) -> list[tuple[str, str]]:
    """Parse ``action:todo_id`` vision todo_delta entries once for consumers."""

    parsed: list[tuple[str, str]] = []
    for value in entries or []:
        if not isinstance(value, str):
            continue
        action, separator, raw_todo_id = value.strip().partition(":")
        todo_id = _compact_text(raw_todo_id, limit=VISION_TODO_DELTA_ID_LIMIT)
        normalized_action = action.strip().lower()
        if (
            separator
            and todo_id
            and normalized_action in (VISION_FRONTIER_TODO_DELTA_ACTIONS)
        ):
            parsed.append((normalized_action, todo_id))
    return parsed


def parse_fallback_declarations(
    agent_vision: dict[str, Any] | None,
) -> list[FallbackDeclaration]:
    """Parse typed fallback declarations written by the TS Vision contract.

    The only supported authoring path is ``agent_vision.fallback_declarations``
    as validated and persisted by the TS-owned ``goal.vision_checkpoint``
    prepare (and mirrored through the status/shared-runtime compact read
    model). Prose mentions, generic ``todo_delta`` actions, and legacy alias
    shapes are not declarations.
    """

    declarations: list[FallbackDeclaration] = []
    if not isinstance(agent_vision, dict):
        return declarations
    source = agent_vision.get("fallback_declarations")
    if not isinstance(source, list):
        return declarations

    seen: set[tuple[str, str | None, str | None]] = set()
    for raw in source[:VISION_FALLBACK_DECLARATION_ENTRY_LIMIT]:
        if not isinstance(raw, dict):
            continue
        declaration_id = _compact_text(
            raw.get("declaration_id"),
            limit=VISION_TODO_DELTA_ID_LIMIT,
        )
        if not declaration_id:
            continue
        target_todo_id = normalize_todo_id(raw.get("target_todo_id"))
        successor_todo_id = normalize_todo_id(raw.get("successor_todo_id"))
        key = (declaration_id, target_todo_id, successor_todo_id)
        if key in seen:
            continue
        seen.add(key)
        declarations.append(
            FallbackDeclaration(
                declaration_id=declaration_id,
                target_todo_id=target_todo_id,
                successor_todo_id=successor_todo_id,
            )
        )
    return declarations


def _blocked_successor_todo_ids(
    agent_todo_summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> set[str]:
    """Ids the blocked-successor wait state itself is waiting on."""

    if not isinstance(agent_todo_summary, dict):
        return set()
    return {
        todo_id
        for todo_id in (
            normalize_todo_id(item.get("todo_id"))
            for item in todo_summary_blocked_successor_items(
                agent_todo_summary,
                agent_id=agent_id,
            )
            if isinstance(item, dict)
        )
        if todo_id
    }


def _blocked_primary_waiting(
    agent_todo_summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> bool:
    """Reuse the blocked-successor wait scope as the primary-blocked signal."""

    if not isinstance(agent_todo_summary, dict):
        return False
    blocker_items = agent_todo_summary.get("current_agent_blocker_items")
    if isinstance(blocker_items, list) and blocker_items:
        return True
    return bool(
        todo_summary_blocked_successor_items(
            agent_todo_summary,
            agent_id=agent_id,
        )
    )


def _vision_has_terminal_disposition(agent_vision: dict[str, Any]) -> bool:
    """Terminal evidence: closed-family state or path_delta.outcome=stop."""

    if goal_vision_state_is_closed(agent_vision.get("state")):
        return True
    path_delta = agent_vision.get("path_delta")
    path_delta = path_delta if isinstance(path_delta, dict) else {}
    return (
        str(path_delta.get("outcome") or "").strip().lower()
        == VISION_FALLBACK_TERMINAL_PATH_OUTCOME
    )


def declared_fallback_gap_from_agent_vision(
    agent_vision: dict[str, Any] | None,
    *,
    agent_todo_summary: dict[str, Any] | None,
    agent_id: str | None,
) -> dict[str, Any] | None:
    """Project one advisory gap for an unresolved declared fallback.

    A fallback direction is declared structurally via the agent vision's
    typed ``fallback_declarations`` contract, which the TS-owned Vision
    prepare validates and persists. Prose mentions never declare a
    fallback, and generic ``todo_delta`` actions are not fallback
    declarations on their own.

    The declared direction is resolved when one of:
    1. A linked Todo sits on the authoritative agent-scoped selectable
       advancement frontier (peer-claimed primary-path Todos do not);
    2. A bounded successor Todo is created or reopened specifically for
       this fallback direction; or
    3. The vision records an explicit terminal disposition (closed-family state
       or path_delta.outcome=stop).

    When the primary path is blocked and none of the resolutions holds, the
    declared fallback would otherwise disappear silently behind the
    blocked-successor wait state, which clears the ordinary acceptance gaps.
    This advisory gap stays in the independent ``fallback_gaps`` projection
    field and never enters the acceptance-gap replan stream.
    """

    if not isinstance(agent_vision, dict):
        return None
    if _vision_has_terminal_disposition(agent_vision):
        return None
    if not _blocked_primary_waiting(
        agent_todo_summary,
        agent_id=agent_id,
    ):
        return None

    declarations = parse_fallback_declarations(agent_vision)
    if not declarations:
        return None

    selectable_ids = agent_scoped_selectable_advancement_todo_ids(
        agent_todo_summary,
        agent_id=agent_id,
    )
    waiting_todo_ids = _blocked_successor_todo_ids(
        agent_todo_summary,
        agent_id=agent_id,
    )
    todo_delta = parse_vision_todo_delta_entries(agent_vision.get("todo_delta"))
    created_or_reopened_ids = {
        todo_id
        for action, todo_id in todo_delta
        if action in VISION_TODO_DELTA_SUCCESSOR_ACTIONS
    }

    unresolved_ids: set[str] = set()
    for declaration in declarations:
        candidate_ids = declaration.candidate_todo_ids - waiting_todo_ids
        if not candidate_ids:
            continue
        # Disposition 1: Runnable on authoritative selectable advancement frontier
        if candidate_ids & selectable_ids:
            continue
        # Disposition 2: Bounded successor created/reopened specifically for this fallback
        if candidate_ids & created_or_reopened_ids:
            continue
        if (
            declaration.successor_todo_id
            and declaration.successor_todo_id in created_or_reopened_ids
        ):
            continue

        unresolved_id = declaration.unresolved_todo_id
        if unresolved_id not in waiting_todo_ids:
            unresolved_ids.add(unresolved_id)

    if not unresolved_ids:
        return None

    gap: dict[str, Any] = {
        "kind": VISION_FALLBACK_GAP_TRIGGER,
        "source": "latest_agent_vision",
        "agent_id": agent_vision.get("agent_id"),
        "state": agent_vision.get("state"),
        "reason_code": VISION_FALLBACK_GAP_REASON_CODE,
        "recommended_action": VISION_FALLBACK_RECOMMENDED_ACTION,
    }
    unresolved_todo_ids = [todo_id for todo_id in sorted(unresolved_ids) if todo_id][
        :VISION_FALLBACK_RUNNABLE_ITEM_LIMIT
    ]
    if unresolved_todo_ids:
        gap["unresolved_todo_ids"] = unresolved_todo_ids
    generated_at = _compact_text(agent_vision.get("generated_at"), limit=80)
    if generated_at:
        gap["generated_at"] = generated_at
    return {key: value for key, value in gap.items() if value is not None}
