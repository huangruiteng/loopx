"""Derived, read-only Goal artifact lifecycle projection.

An operator looking at a long-running Goal can see todo counts, quota state and
the latest run classification, but still has to reconstruct three answers from
them: where the Goal is in its lifecycle, which milestones it has reached, and
which guard blocks the next step and who owns it.

This module derives those answers from state LoopX already owns. It is a pure
function over an already-collected status/goal payload: it reads no files,
writes no state, and creates no new authority. Milestones and lifecycle phases
are projections, never stored fields.

Milestone reachability starts from markers the Goal declares, and falls back to
evidence the run history already recorded. Guards are open owner decisions and
unmet evidence preconditions. Next transitions come from the existing
frontier/lane derivation instead of a second state machine.
"""

from __future__ import annotations

from typing import Any

GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION = (
    "goal_artifact_lifecycle_projection_v0"
)

# Derived labels, not a stored enum. They name the operator's question, and a
# Goal may move between them without any durable transition.
PHASE_STARTING = "starting"
PHASE_QUALIFYING = "qualifying"
PHASE_WAITING_OWNER = "waiting_owner"
PHASE_CLOSING = "closing"
PHASE_CLOSED = "closed"

GUARD_KIND_OWNER_DECISION = "owner_decision"
GUARD_KIND_EVIDENCE = "evidence_precondition"

_TERMINAL_GOAL_STATUSES = {"closed", "retired", "archived", "done", "complete"}

# A material run outcome that a Goal's own acceptance can rest on.
_MATERIAL_OUTCOMES = {"primary_goal_outcome", "outcome_progress", "multi_surface"}


def _compact_text(value: Any, *, limit: int = 240) -> str | None:
    """Bound one public-safe label; never carry a raw body or path."""

    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    if not collapsed:
        return None
    return collapsed[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _goal_status(goal: dict[str, Any]) -> str:
    return str(goal.get("status") or "").strip().lower()


def _is_closed(goal: dict[str, Any]) -> bool:
    return _goal_status(goal) in _TERMINAL_GOAL_STATUSES


def _declared_milestones(goal: dict[str, Any]) -> list[dict[str, Any]]:
    """Read Goal-declared acceptance markers, if the Goal records any."""

    acceptance = _mapping(goal.get("acceptance"))
    raw = _list(acceptance.get("milestones")) or _list(goal.get("milestones"))
    milestones: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        record = _mapping(item)
        if not isinstance(item, str) and not record:
            continue
        milestone_id = (
            _compact_text(item, limit=120) if isinstance(item, str)
            else _compact_text(record.get("id") or record.get("milestone_id"), limit=120)
        )
        if not milestone_id:
            milestone_id = f"milestone_{index + 1}"
        label = (
            None if isinstance(item, str)
            else _compact_text(record.get("label") or record.get("summary"))
        )
        milestones.append(
            {
                "id": milestone_id,
                "label": label or milestone_id,
                "reached": False,
                "reached_evidence_refs": [],
                "source": "declared",
            }
        )
    return milestones


def _evidence_milestones(run_history: dict[str, Any]) -> list[dict[str, Any]]:
    """Fall back to material evidence the run history already recorded."""

    milestones: list[dict[str, Any]] = []
    seen: set[str] = set()
    for run in _list(run_history.get("latest_runs")):
        record = _mapping(run)
        if not record:
            continue
        outcome = str(record.get("delivery_outcome") or "").strip()
        scale = str(record.get("delivery_batch_scale") or "").strip()
        classification = str(record.get("classification") or "").strip()
        if outcome not in _MATERIAL_OUTCOMES and scale != "multi_surface":
            continue
        milestone_id = outcome or scale or classification
        if not milestone_id or milestone_id in seen:
            continue
        seen.add(milestone_id)
        reference = _compact_text(record.get("evidence_ref") or record.get("run_id"), limit=120)
        milestones.append(
            {
                "id": milestone_id,
                "label": _compact_text(record.get("recommended_action"), limit=160)
                or milestone_id,
                "reached": True,
                "reached_evidence_refs": [reference] if reference else [],
                "source": "evidence",
            }
        )
    return milestones


def _milestones(
    goal: dict[str, Any],
    run_history: dict[str, Any],
) -> list[dict[str, Any]]:
    declared = _declared_milestones(goal)
    evidence = _evidence_milestones(run_history)
    if not declared:
        return evidence
    # A declared marker is a claim about what the Goal intends to reach, not
    # proof that it did. It counts as reached only when evidence already
    # records that outcome, or when the Goal marks it reached explicitly.
    reached_outcomes = {item["id"] for item in evidence if item["reached"]}
    for milestone in declared:
        milestone["reached"] = milestone["id"] in reached_outcomes
    return declared + [item for item in evidence if item["id"] not in {m["id"] for m in declared}]


def _guards(
    user_summary: dict[str, Any],
    acceptance_gaps: list[Any],
    *,
    agent_id: str | None,
) -> list[dict[str, Any]]:
    """Open owner decisions and unmet evidence preconditions."""

    guards: list[dict[str, Any]] = []
    for item in _list(user_summary.get("gate_open_items")):
        record = _mapping(item)
        if not record:
            continue
        blocking_agent = _compact_text(record.get("blocks_agent"), limit=120)
        guards.append(
            {
                "id": _compact_text(record.get("todo_id"), limit=120) or "owner_gate",
                "kind": GUARD_KIND_OWNER_DECISION,
                "blocked": True,
                "owner": "user",
                "decision_scope": _compact_text(record.get("action_kind"), limit=120),
                "evidence_required": False,
                "blocks_agent": blocking_agent,
            }
        )
    for gap in acceptance_gaps:
        record = _mapping(gap)
        if not record:
            continue
        guards.append(
            {
                "id": _compact_text(record.get("kind"), limit=120) or "acceptance_gap",
                "kind": GUARD_KIND_EVIDENCE,
                "blocked": True,
                "owner": "agent",
                "decision_scope": None,
                "evidence_required": True,
                "agent_id": _compact_text(record.get("agent_id"), limit=120) or agent_id,
            }
        )
    return guards


def _lifecycle_phase(
    goal: dict[str, Any],
    *,
    guards: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    agent_summary: dict[str, Any],
) -> str:
    if _is_closed(goal):
        return PHASE_CLOSED
    if any(guard["kind"] == GUARD_KIND_OWNER_DECISION for guard in guards):
        return PHASE_WAITING_OWNER
    open_count = agent_summary.get("open_count")
    total_open = open_count if isinstance(open_count, int) and not isinstance(open_count, bool) else 0
    if not milestones and total_open == 0:
        return PHASE_STARTING
    if total_open == 0:
        return PHASE_CLOSING
    return PHASE_QUALIFYING


def _next_transitions(
    goal: dict[str, Any],
    *,
    phase: str,
    guards: list[dict[str, Any]],
    work_lane: dict[str, Any],
) -> list[dict[str, Any]]:
    """Reuse the existing lane/frontier derivation instead of a second machine."""

    blocking = [guard for guard in guards if guard["blocked"]]
    if _is_closed(goal):
        return []
    lane = _compact_text(work_lane.get("lane"), limit=120)
    obligation = _compact_text(work_lane.get("obligation"), limit=120)
    if blocking:
        return [
            {
                "target_phase": phase,
                "precondition": (
                    "resolve the open owner decision"
                    if any(guard["kind"] == GUARD_KIND_OWNER_DECISION for guard in blocking)
                    else "produce the required evidence"
                ),
                "reason_codes": ["guard_open"],
            }
        ]
    if phase == PHASE_CLOSING:
        return [
            {
                "target_phase": PHASE_CLOSED,
                "precondition": "record the terminal no-follow-up outcome",
                "reason_codes": ["no_open_agent_work"],
            }
        ]
    if lane:
        return [
            {
                "target_phase": PHASE_QUALIFYING,
                "precondition": obligation or "advance the selected lane",
                "reason_codes": ["work_lane_selected"],
            }
        ]
    return []


def build_goal_artifact_lifecycle_projection(
    *,
    goal_id: str,
    goal: dict[str, Any] | None,
    user_todo_summary: dict[str, Any] | None = None,
    agent_todo_summary: dict[str, Any] | None = None,
    run_history: dict[str, Any] | None = None,
    work_lane_contract: dict[str, Any] | None = None,
    acceptance_gaps: list[Any] | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Derive the read-only lifecycle projection for one Goal.

    Every input is a payload the caller already collected; this function reads
    nothing itself and grants no authority.
    """

    goal_record = _mapping(goal)
    user_summary = _mapping(user_todo_summary)
    agent_summary = _mapping(agent_todo_summary)
    history = _mapping(run_history)
    lane = _mapping(work_lane_contract)
    gaps = [gap for gap in _list(acceptance_gaps) if _mapping(gap)]

    milestones = _milestones(goal_record, history)
    guards = _guards(user_summary, gaps, agent_id=agent_id)
    phase = _lifecycle_phase(
        goal_record, guards=guards, milestones=milestones, agent_summary=agent_summary
    )
    return {
        "schema_version": GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION,
        "goal_id": str(goal_id),
        "lifecycle_phase": phase,
        "milestones": milestones,
        "guards": guards,
        "next_transitions": _next_transitions(
            goal_record, phase=phase, guards=guards, work_lane=lane
        ),
    }


__all__ = [
    "GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION",
    "GUARD_KIND_EVIDENCE",
    "GUARD_KIND_OWNER_DECISION",
    "PHASE_CLOSED",
    "PHASE_CLOSING",
    "PHASE_QUALIFYING",
    "PHASE_STARTING",
    "PHASE_WAITING_OWNER",
    "build_goal_artifact_lifecycle_projection",
]
