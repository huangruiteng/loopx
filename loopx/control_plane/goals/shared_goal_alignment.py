"""Read-only shared goal alignment projection adapter (RFC Stage 1).

This adapter collects typed facts for one registered Agent around one shared
Goal — registry identity, the markdown active state, the append-only state
event log, Todo claim/lease fields, and recorded replan obligations — and
asks the TypeScript-owned reducer (``goal.shared_goal_alignment.project``)
to project ``shared_goal_alignment_v0``.

Derivation invariants (RFC shared-goal-alignment-and-governed-amendment-v0
§3.3): every projected field is derived from typed facts only. Shared
``Next Action`` prose, agent vision prose, and chat prose are never inputs.

The projection is strictly read-only: no writer path is touched, and no
approval or escalation semantics exist here. ``source_basis_digest`` is a
typed source-facts basis summary (goal status, registered agents, and
event-log basis facts), not a canonical intent-envelope digest — the full
RFC §3.1 envelope (objective, non-goals, acceptance, permission scope,
terminal conditions) has no typed storage yet, so nothing here claims
canonical intent identity.

Basis semantics: the only goal-level monotonic sequence carrier on this
codebase is the state event log's ``append_sequence``, so
``state_event_basis_sequence`` reports that event projection basis — it is
NOT a canonical goal/intent revision. Goals without a parsable
``events.jsonl`` project ``revision_basis="markdown_active_state"`` with
``state_event_basis_sequence=0`` and every Agent frontier ``unbound``;
drift is then reported as ``frontier_basis_unverifiable`` instead of a
fabricated behind fact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...agent_registry import registered_agent_ids_for_goal
from ...event_sourced_state import (
    AppendOnlyStateEventStore,
    StateEventError,
    build_state_projection,
    event_sort_key,
)
from ...registry import registry_goals, resolve_state_file
from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from ..todos.active_state_todo_parser import parse_active_state_todos
from ..todos.contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_id,
)
from ..todos.projection import (
    todo_advancement_frontier_counts,
    todo_item_is_actionable_open,
)
from ..work_items.local_lease_record import lease_epoch, read_lease
from ..work_items.task_lease import lease_is_active, task_lease_path
from .active_state_event_projection import state_event_log_candidates
from .active_state_metadata import parse_state_frontmatter
from .goal_frontier import (
    autonomous_replan_is_required,
    select_autonomous_replan_obligation,
)
from .path_resolution import resolve_goal_local_path

SHARED_GOAL_ALIGNMENT_EFFECT_METHOD = "goal.shared_goal_alignment.project"
SHARED_GOAL_ALIGNMENT_REQUEST_SCHEMA_VERSION = "shared_goal_alignment_request_v0"
SHARED_GOAL_ALIGNMENT_SCHEMA_VERSION = "shared_goal_alignment_v0"
REVISION_BASIS_STATE_EVENT_LOG = "state_event_log"
REVISION_BASIS_MARKDOWN_ACTIVE_STATE = "markdown_active_state"
BASIS_SOURCE_STATE_EVENT_LOG = "state_event_log"
BASIS_SOURCE_UNBOUND = "unbound"
DEFAULT_REGISTRY_RELATIVE_PATH = Path(".loopx") / "registry.json"


def _canonical_digest(value: object) -> str:
    # Local copy of the repository digest recipe: control_plane must not
    # import loopx.capabilities (m6 control_plane_outward_dependency).
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _registered_goal(
    registry_payload: Mapping[str, Any],
    *,
    goal_id: str,
) -> dict[str, Any]:
    for goal in registry_goals(dict(registry_payload)):
        if str(goal.get("id") or "") == goal_id:
            return goal
    raise ValueError(f"goal is not registered: {goal_id}")


def _load_state_event_facts(
    goal: Mapping[str, Any],
    *,
    state_path: Path,
) -> dict[str, Any] | None:
    """Load the first parsable state event log for the goal, read-only."""

    for event_log_path in state_event_log_candidates(
        dict(goal),
        state_path=state_path,
        resolve_goal_local_path=resolve_goal_local_path,
    ):
        if not event_log_path.exists():
            continue
        try:
            events = AppendOnlyStateEventStore(event_log_path).load()
            if not events:
                continue
            projection = build_state_projection(
                events,
                goal_id=str(goal.get("id") or "") or None,
            )
        except (OSError, StateEventError):
            continue
        return {"events": events, "projection": projection}
    return None


def _agent_frontier_basis(
    event_facts: Mapping[str, Any] | None,
    *,
    agent_id: str,
) -> dict[str, Any]:
    """Derive the Agent's frontier basis from its own attributed events.

    ``based_on_state_event_sequence`` is the highest append sequence among
    events whose ``actor_agent_id`` belongs to this Agent. Events attributed
    to peers never advance another Agent's basis.
    """

    events = event_facts.get("events") if event_facts else None
    if not isinstance(events, list):
        return {
            "based_on_state_event_sequence": None,
            "basis_source": BASIS_SOURCE_UNBOUND,
            "last_agent_event_id": None,
        }
    based_on: int | None = None
    last_agent_event_id: str | None = None
    for event in sorted(
        (item for item in events if isinstance(item, dict)),
        key=event_sort_key,
    ):
        actor = normalize_todo_claimed_by(event.get("actor_agent_id"))
        if actor != agent_id:
            continue
        try:
            sequence = int(event.get("append_sequence") or 0)
        except (TypeError, ValueError):
            continue
        if sequence < 1:
            continue
        based_on = sequence
        event_id = str(event.get("event_id") or "").strip()
        last_agent_event_id = event_id or None
    if based_on is None:
        return {
            "based_on_state_event_sequence": None,
            "basis_source": BASIS_SOURCE_UNBOUND,
            "last_agent_event_id": None,
        }
    return {
        "based_on_state_event_sequence": based_on,
        "basis_source": BASIS_SOURCE_STATE_EVENT_LOG,
        "last_agent_event_id": last_agent_event_id,
    }


def _source_basis_facts_envelope(
    *,
    goal_id: str,
    goal_status: str | None,
    registered_agents: list[str],
    revision_basis: str,
    last_append_sequence: int | None,
    source_checksum: str | None,
    state_updated_at: str | None,
) -> dict[str, Any]:
    return {
        "goal_id": goal_id,
        "goal_status": goal_status,
        "registered_agents": sorted(registered_agents),
        "revision_basis": revision_basis,
        "last_append_sequence": last_append_sequence,
        "source_checksum": source_checksum,
        "state_updated_at": state_updated_at,
    }


def _parsed_active_state(
    state_text: str,
    *,
    goal: Mapping[str, Any],
    state_path: Path,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    parsed = parse_active_state_todos(
        state_text,
        goal=dict(goal),
        state_path=state_path,
        item_limit=None,
    )
    summary = parsed.get("agent_todos") if isinstance(parsed, dict) else None
    items = summary.get("items") if isinstance(summary, dict) else None
    if not isinstance(summary, dict):
        return None, []
    if not isinstance(items, list):
        return summary, []
    return summary, [item for item in items if isinstance(item, dict)]


def _frontier_claim_items(
    items: list[dict[str, Any]],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if todo_item_is_actionable_open(item)
        and item.get("task_class") == TODO_TASK_CLASS_ADVANCEMENT
        and normalize_todo_claimed_by(item.get("claimed_by")) == agent_id
    ]


def _unclaimed_eligible_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if todo_item_is_actionable_open(item)
        and item.get("task_class") == TODO_TASK_CLASS_ADVANCEMENT
        and not normalize_todo_claimed_by(item.get("claimed_by"))
    ]


def _peer_claimed_bound_todo_ids(
    items: list[dict[str, Any]],
    *,
    agent_id: str,
) -> list[str]:
    todo_ids: list[str] = []
    for item in items:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if not claimed_by or claimed_by == agent_id:
            continue
        if not todo_item_is_actionable_open(item):
            continue
        if item.get("task_class") != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        if normalize_todo_bound_agent(item.get("bound_agent")) != agent_id:
            continue
        todo_id = normalize_todo_id(item.get("todo_id"))
        if todo_id and todo_id not in todo_ids:
            todo_ids.append(todo_id)
    return todo_ids


def _claim_lease_facts(
    todo_id: str,
    *,
    runtime_root: Path | None,
    goal_id: str,
) -> dict[str, Any]:
    if runtime_root is None:
        return {"lease_epoch": None, "lease_owner": None}
    lease = read_lease(
        task_lease_path(
            runtime_root=runtime_root,
            goal_id=goal_id,
            todo_id=todo_id,
        )
    )
    if not lease or not lease_is_active(lease):
        return {"lease_epoch": None, "lease_owner": None}
    owner = normalize_todo_claimed_by(lease.get("owner"))
    if not owner:
        # An active hard lease without a valid owner is corrupt authority.
        # Projecting it as lease facts with a null owner would let the
        # reducer treat the broken lease as "no conflict"; fail closed
        # before the typed request is built instead.
        raise ValueError(
            "active task lease has no valid owner: "
            f"goal={goal_id} todo={todo_id}"
        )
    return {"lease_epoch": lease_epoch(lease), "lease_owner": owner}


def project_shared_goal_alignment(
    *,
    goal_id: str,
    agent_id: str | None,
    project: Path,
    registry_path: Path | None = None,
    runtime_root: Path | None = None,
    status_item: Mapping[str, Any] | None = None,
    project_asset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project the read-only ``shared_goal_alignment_v0`` view for one Agent."""

    normalized_goal_id = str(goal_id or "").strip()
    if not normalized_goal_id:
        raise ValueError("goal_id must be a non-empty registered goal id")
    normalized_agent_id = normalize_todo_claimed_by(agent_id)
    if not normalized_agent_id:
        raise ValueError("agent_id must be a public-safe agent id")

    effective_registry_path = (
        registry_path if registry_path is not None
        else project / DEFAULT_REGISTRY_RELATIVE_PATH
    )
    try:
        registry_payload = json.loads(
            effective_registry_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        raise ValueError(
            f"goal registry is unreadable: {effective_registry_path}"
        ) from None
    if not isinstance(registry_payload, dict):
        raise TypeError("goal registry must contain a JSON object")
    goal = _registered_goal(registry_payload, goal_id=normalized_goal_id)

    registered_agents = registered_agent_ids_for_goal(goal)
    if normalized_agent_id not in registered_agents:
        raise ValueError(
            f"agent is not registered for goal {normalized_goal_id}: "
            f"{normalized_agent_id}"
        )

    state_file = resolve_state_file(project, goal.get("state_file"))
    if state_file is None or not state_file.is_file():
        raise ValueError(
            f"goal state file is missing for {normalized_goal_id}"
        )
    state_text = state_file.read_text(encoding="utf-8")

    event_facts = _load_state_event_facts(goal, state_path=state_file)
    frontmatter = parse_state_frontmatter(state_text)
    state_updated_at = str(frontmatter.get("updated_at") or "").strip() or None
    goal_status = str(goal.get("status") or "").strip() or (
        str(frontmatter.get("status") or "").strip() or None
    )

    if event_facts is not None:
        projection = event_facts["projection"]
        revision_basis = REVISION_BASIS_STATE_EVENT_LOG
        try:
            basis_sequence = int(projection.get("last_append_sequence") or 0)
        except (TypeError, ValueError):
            basis_sequence = 0
        source_checksum = (
            str(projection.get("source_checksum") or "").strip() or None
        )
    else:
        revision_basis = REVISION_BASIS_MARKDOWN_ACTIVE_STATE
        basis_sequence = 0
        source_checksum = None

    source_basis_digest = _canonical_digest(
        _source_basis_facts_envelope(
            goal_id=normalized_goal_id,
            goal_status=goal_status,
            registered_agents=registered_agents,
            revision_basis=revision_basis,
            last_append_sequence=(
                basis_sequence
                if revision_basis == REVISION_BASIS_STATE_EVENT_LOG
                else None
            ),
            source_checksum=source_checksum,
            state_updated_at=state_updated_at,
        )
    )
    source_basis = {
        "state_event_basis_sequence": basis_sequence,
        "source_basis_digest": source_basis_digest,
        "revision_basis": revision_basis,
        "state_updated_at": state_updated_at,
    }

    frontier_basis = _agent_frontier_basis(
        event_facts,
        agent_id=normalized_agent_id,
    )

    agent_summary, items = _parsed_active_state(
        state_text,
        goal=goal,
        state_path=state_file,
    )
    frontier_counts = todo_advancement_frontier_counts(
        agent_summary,
        agent_id=normalized_agent_id,
    )

    effective_runtime_root = (
        runtime_root
        if runtime_root is not None
        else _runtime_root_from_registry(registry_payload)
    )
    claims = []
    for item in _frontier_claim_items(items, agent_id=normalized_agent_id):
        todo_id = normalize_todo_id(item.get("todo_id"))
        if not todo_id:
            continue
        claims.append(
            {
                "todo_id": todo_id,
                "claimed_by": normalized_agent_id,
                **_claim_lease_facts(
                    todo_id,
                    runtime_root=effective_runtime_root,
                    goal_id=normalized_goal_id,
                ),
            }
        )

    unclaimed_eligible = [
        {
            "todo_id": normalize_todo_id(item.get("todo_id")),
            "task_class": TODO_TASK_CLASS_ADVANCEMENT,
            **(
                {"action_kind": str(item.get("action_kind"))}
                if str(item.get("action_kind") or "").strip()
                else {}
            ),
        }
        for item in _unclaimed_eligible_items(items)
        if normalize_todo_id(item.get("todo_id"))
    ]

    replan_obligation = select_autonomous_replan_obligation(
        dict(status_item) if isinstance(status_item, Mapping) else {},
        dict(project_asset) if isinstance(project_asset, Mapping) else None,
        agent_id=normalized_agent_id,
    )

    request = {
        "schema_version": SHARED_GOAL_ALIGNMENT_REQUEST_SCHEMA_VERSION,
        "goal_id": normalized_goal_id,
        "agent_id": normalized_agent_id,
        "source_basis": source_basis,
        "frontier_basis": frontier_basis,
        "frontier_counts": frontier_counts,
        "claims": claims,
        "unclaimed_eligible": unclaimed_eligible,
        "peer_claimed_bound_todo_ids": _peer_claimed_bound_todo_ids(
            items,
            agent_id=normalized_agent_id,
        ),
        "open_lane_replan_obligation_required": (
            autonomous_replan_is_required(replan_obligation)
        ),
    }
    try:
        result = effect_runtime_result(
            SHARED_GOAL_ALIGNMENT_EFFECT_METHOD,
            request,
        )
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not isinstance(result, Mapping) or (
        result.get("schema_version") != SHARED_GOAL_ALIGNMENT_SCHEMA_VERSION
        or result.get("read_only") is not True
        or result.get("goal_id") != normalized_goal_id
        or result.get("agent_id") != normalized_agent_id
        or not isinstance(result.get("drift_facts"), list)
        or not isinstance(result.get("conflict_facts"), list)
    ):
        raise RuntimeError("TypeScript shared goal alignment shape mismatch")
    return dict(result)


def _runtime_root_from_registry(
    registry_payload: Mapping[str, Any],
) -> Path | None:
    raw = registry_payload.get("common_runtime_root")
    text = str(raw or "").strip()
    return Path(text).expanduser() if text else None
