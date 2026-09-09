"""Read-only shared goal alignment projection adapter (RFC Stage 1).

This adapter collects typed facts for one registered Agent around one shared
Goal — registry identity, the selected Todo/lease source, the append-only state
event log, Todo claim/lease fields, and recorded replan obligations — and
asks the TypeScript-owned reducer (``goal.shared_goal_alignment.project``)
to project ``shared_goal_alignment_v0``.

Derivation invariants (RFC shared-goal-alignment-and-governed-amendment-v0
§3.3): every projected field is derived from typed facts only. Shared
``Next Action`` prose, agent vision prose, and chat prose are never inputs.

The projection is strictly read-only: no writer path is touched, and no
approval or escalation semantics exist here. ``source_basis_digest`` is a
typed source-facts basis summary (goal status, registered agents, and
event-log basis facts, and canonical Todo revision when promoted), not a canonical intent-envelope digest — the full
RFC §3.1 envelope (objective, non-goals, acceptance, permission scope,
terminal conditions) has no typed storage yet, so nothing here claims
canonical intent identity.

Basis semantics: the only goal-level monotonic sequence carrier on this
codebase is the state event log's ``append_sequence``, so
``state_event_basis_sequence`` reports that event projection basis — it is
NOT a canonical goal/intent revision. Goals without a parsable
``events.jsonl`` use sequence 0 and an unbound Agent frontier. Before promotion
this is ``markdown_active_state``; after promotion it is ``canonical_todo_snapshot``
with a separate ``todo_basis`` token, never a fabricated event sequence;
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
from ...registry import registry_goals
from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from ..todos.contract import normalize_todo_claimed_by
from .shared_goal_work_source import SharedGoalWorkSource, read_shared_goal_work_source
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
    todo_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "goal_id": goal_id,
        "goal_status": goal_status,
        "registered_agents": sorted(registered_agents),
        "revision_basis": revision_basis,
        "last_append_sequence": last_append_sequence,
        "source_checksum": source_checksum,
        "state_updated_at": state_updated_at,
        **({"todo_basis": todo_basis} if todo_basis is not None else {}),
    }


def project_shared_goal_alignment(
    *, goal_id: str, agent_id: str | None, project: Path,
    registry_path: Path | None = None, runtime_root: Path | None = None,
    status_item: Mapping[str, Any] | None = None,
    project_asset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Public read-only entrypoint; callers cannot inject the Todo snapshot."""
    return _project_shared_goal_alignment(goal_id=goal_id, agent_id=agent_id,
        project=project, registry_path=registry_path, runtime_root=runtime_root,
        status_item=status_item, project_asset=project_asset)


def _project_shared_goal_alignment(
    *,
    goal_id: str,
    agent_id: str | None,
    project: Path,
    registry_path: Path | None = None,
    runtime_root: Path | None = None,
    status_item: Mapping[str, Any] | None = None,
    project_asset: Mapping[str, Any] | None = None,
    work_source: SharedGoalWorkSource | None = None,
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
        raise ValueError("goal registry must contain a JSON object")
    goal = _registered_goal(registry_payload, goal_id=normalized_goal_id)

    registered_agents = registered_agent_ids_for_goal(goal)
    if normalized_agent_id not in registered_agents:
        raise ValueError(
            f"agent is not registered for goal {normalized_goal_id}: "
            f"{normalized_agent_id}"
        )

    effective_runtime_root = runtime_root if runtime_root is not None else _runtime_root_from_registry(registry_payload)
    source = work_source or read_shared_goal_work_source(
        goal=goal, project=project, runtime_root=effective_runtime_root,
    )
    if source.goal_id != normalized_goal_id:
        raise ValueError("shared work snapshot belongs to another Goal")
    state_file, state_text = source.state_path, source.state_text

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
        revision_basis = ("canonical_todo_snapshot" if source.canonical_basis is not None
            else REVISION_BASIS_MARKDOWN_ACTIVE_STATE)
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
            todo_basis=source.canonical_basis,
        )
    )
    source_basis = {
        "state_event_basis_sequence": basis_sequence,
        "source_basis_digest": source_basis_digest,
        "revision_basis": revision_basis,
        "state_updated_at": state_updated_at,
        **({"todo_basis": source.canonical_basis} if source.canonical_basis is not None else {}),
    }

    frontier_basis = _agent_frontier_basis(
        event_facts,
        agent_id=normalized_agent_id,
    )

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
        "work_items": source.items,
        "observed_at": source.observed_at,
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
