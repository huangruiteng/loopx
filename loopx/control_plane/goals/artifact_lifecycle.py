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

import re
from typing import Any

from ...public_safe_text import find_private_text_match
from ..runtime.public_safety import public_safe_compact_text, validate_public_safe_value
from .acceptance_observation import build_goal_acceptance_observation
from ..work_items.delivery_outcome import (
    MATERIAL_DELIVERY_OUTCOMES,
    PROGRESS_DELIVERY_OUTCOMES,
    normalize_delivery_outcome,
)

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

# Provider token shapes the shared private-text rules do not cover. A run
# history reference is free text, so a leaked token there must never reach a
# public projection just because the shared corpus did not list its prefix.
_TOKEN_SHAPES = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16})\b"
)

def _compact_text(value: Any, *, limit: int = 240) -> str | None:
    """Validate the complete source before bounding any public label/ref."""
    if not isinstance(value, str):
        return None
    try:
        validate_public_safe_value(value)
    except ValueError:
        return None
    # Preserve the stricter existing private-text/provider-token contract too;
    # these checks supplement, never replace, the shared public-safety owner.
    if find_private_text_match(value) or _TOKEN_SHAPES.search(value):
        return None
    return public_safe_compact_text(value, limit=limit)


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
        outcome = normalize_delivery_outcome(record.get("delivery_outcome"))
        # Only a canonical material delivery outcome is Goal evidence. The batch
        # scale describes how wide a delivery was, never whether it advanced the
        # Goal, so it cannot promote `surface_only` into a reached milestone.
        if outcome is None or outcome not in MATERIAL_DELIVERY_OUTCOMES:
            continue
        milestone_id = outcome.value
        if milestone_id in seen:
            continue
        seen.add(milestone_id)
        # Collected history exposes a timestamp, not always a public run id.
        # Keep that existing locator; never publish its JSON/Markdown path.
        reference = _compact_text(
            record.get("evidence_ref") or record.get("run_id") or record.get("generated_at"),
            limit=120,
        )
        milestones.append(
            {
                "id": milestone_id,
                "label": _compact_text(record.get("recommended_action"), limit=160)
                or milestone_id,
                # Materiality decides what history retains; only the canonical
                # progress outcomes decide what the Goal actually advanced.
                # `outcome_gap` is material evidence of a recorded gap, so it
                # stays visible here as an unreached marker.
                "reached": outcome in PROGRESS_DELIVERY_OUTCOMES,
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
    # records that outcome.
    reached_outcomes = {item["id"] for item in evidence if item["reached"]}
    for milestone in declared:
        milestone["reached"] = milestone["id"] in reached_outcomes
    return declared + [item for item in evidence if item["id"] not in {m["id"] for m in declared}]


def _guards(
    observation: dict[str, Any],
    acceptance_gaps: list[Any],
    *,
    agent_id: str | None,
) -> list[dict[str, Any]]:
    """Open owner decisions and unmet evidence preconditions."""

    guards: list[dict[str, Any]] = []
    for record in _list(observation.get("guards")):
        if not _mapping(record):
            continue
        guards.append({
            "id": _compact_text(record.get("todo_id"), limit=120) or "operator_gate",
            "kind": GUARD_KIND_OWNER_DECISION,
            "blocked": True,
            "owner": _compact_text(record.get("owner"), limit=120)
            or ("user" if record.get("kind") == "user_gate" else "controller"),
            "decision_scope": _compact_text(record.get("decision_scope")),
            "evidence_required": bool(record.get("evidence_required")),
            "blocks_agent": _compact_text(record.get("blocks_agent"), limit=120),
        })
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
                "agent_id": _compact_text(record.get("agent_id") or record.get("owner"), limit=120)
                or _compact_text(agent_id, limit=120),
            }
        )
    return guards


def _unobserved_acceptance_sources(observation: dict[str, Any]) -> list[str]:
    """Name the acceptance sources the bounded observation could not read.

    `goal_acceptance_observation_projection_v0` reports what it could not
    observe rather than an acceptance verdict, so this projection surfaces
    those sources on the closeout step instead of deriving a second completion
    rule from the same runs.
    """

    return [
        text for text in (
            _compact_text(source, limit=60)
            for source in _list(observation.get("missing_sources"))
        ) if text
    ]


def _lifecycle_phase(
    goal: dict[str, Any],
    *,
    guards: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    agent_summary: dict[str, Any],
    work_lane: dict[str, Any],
) -> str:
    if _is_closed(goal):
        return PHASE_CLOSED
    if any(guard["kind"] == GUARD_KIND_OWNER_DECISION for guard in guards):
        return PHASE_WAITING_OWNER
    if guards or work_lane.get("must_attempt_work") is True:
        return PHASE_QUALIFYING
    open_count = agent_summary.get("open_count")
    if not isinstance(open_count, int) or isinstance(open_count, bool):
        # An omitted/bounded source is not evidence that no work remains.
        return PHASE_QUALIFYING if milestones or guards else PHASE_STARTING
    total_open = open_count
    if not milestones and total_open == 0:
        return PHASE_STARTING
    # An unclaimed-acceptance Goal is never closing: running out of open agent
    # work is not the same as having reached the acceptance markers, and a
    # recorded gap is an unreached marker rather than progress.
    unreached = any(milestone["reached"] is not True for milestone in milestones)
    if total_open == 0 and not unreached:
        return PHASE_CLOSING
    return PHASE_QUALIFYING


def _next_transitions(
    goal: dict[str, Any],
    *,
    phase: str,
    guards: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    work_lane: dict[str, Any],
    observation: dict[str, Any],
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
    # An existing work-lane constraint outranks this projection's own reading
    # of open work: the lane owner decides what runs next.
    if lane:
        return [
            {
                "target_phase": PHASE_QUALIFYING,
                "precondition": obligation or "advance the selected lane",
                "reason_codes": ["work_lane_selected"],
            }
        ]
    unreached = [
        milestone["id"] for milestone in milestones if milestone["reached"] is not True
    ]
    if unreached:
        return [
            {
                "target_phase": PHASE_QUALIFYING,
                "precondition": "reach the unreached acceptance milestones with evidence",
                "reason_codes": ["milestone_unreached"],
            }
        ]
    if phase == PHASE_CLOSING:
        # Closing is the todo-completion reading this RFC adopts; it is not an
        # acceptance verdict. When the acceptance owner could not read some of
        # its sources, the closeout step says so instead of implying a verified
        # acceptance, and the reader keeps the decision.
        unobserved = _unobserved_acceptance_sources(observation)
        precondition = "record the terminal no-follow-up outcome"
        reason_codes = ["no_open_agent_work"]
        if unobserved:
            precondition += "; this readout could not observe " + ", ".join(unobserved)
            reason_codes.append("acceptance_unverified")
        return [
            {
                "target_phase": PHASE_CLOSED,
                "precondition": precondition,
                "reason_codes": reason_codes,
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
    attention_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive the read-only lifecycle projection for one Goal.

    Every input is a payload the caller already collected; this function reads
    nothing itself and grants no authority.
    """

    goal_record = _mapping(goal)
    user_summary = _mapping(user_todo_summary)
    agent_summary = _mapping(agent_todo_summary)
    raw_history = _mapping(run_history)
    runs = list(_list(raw_history.get("latest_runs")))
    # The collector already preserves semantic evidence beyond the display/
    # recent-run window. Reuse that retained state instead of widening a limit.
    for context in _list(_mapping(raw_history.get("semantic_history")).get("agents")):
        for key in ("latest_material_milestone_run", "latest_agent_vision_run"):
            retained = _mapping(context).get(key)
            if _mapping(retained) and retained not in runs:
                runs.append(retained)
    history = {"latest_runs": [
        record for record in runs
        if _mapping(record) and record.get("goal_id") in (None, goal_id)
    ]}
    lane = _mapping(work_lane_contract)
    observation = build_goal_acceptance_observation(
        {**goal_record, "id": goal_id, **history},
        attention_item if attention_item is not None else {"user_todos": user_summary},
    )
    gaps = [gap for gap in _list(acceptance_gaps) if _mapping(gap)]
    if acceptance_gaps is None:
        gaps = _list(observation.get("acceptance_gaps"))
    milestones = _milestones(goal_record, history)
    guards = _guards(observation, gaps, agent_id=agent_id)
    phase = _lifecycle_phase(
        goal_record, guards=guards, milestones=milestones, agent_summary=agent_summary,
        work_lane=lane,
    )
    return {
        "schema_version": GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION,
        "goal_id": _compact_text(goal_id, limit=120) or "unknown",
        "lifecycle_phase": phase,
        "milestones": milestones,
        "guards": guards,
        "next_transitions": _next_transitions(
            goal_record,
            phase=phase,
            guards=guards,
            milestones=milestones,
            work_lane=lane,
            observation=observation,
        ),
    }


def attach_goal_artifact_lifecycle_projections(
    payload: dict[str, Any], *, history: dict[str, Any]
) -> None:
    """Attach one bounded lifecycle projection to every projected Goal.

    Reads only payloads status collection already gathered, so the operator
    readout costs no extra IO and grants no authority. A Goal the projection
    cannot derive from is left without the key rather than given a placeholder.
    """

    sources = {str(goal.get("id")): goal for goal in _list(history.get("goals")) if _mapping(goal)}
    run_history = _mapping(payload.get("run_history"))
    items = _list(_mapping(payload.get("attention_queue")).get("items"))
    for goal in _list(run_history.get("goals")):
        record = _mapping(goal)
        goal_id = str(record.get("id") or "").strip()
        if not goal_id:
            continue
        source = {**record, **sources.get(goal_id, {})}
        item = next(
            (row for row in items if _mapping(row).get("goal_id") == goal_id), None
        )
        attention = _mapping(item)
        asset = _mapping(attention.get("project_asset"))
        frontier = _mapping(attention.get("goal_frontier_projection") or asset.get("goal_frontier_projection"))
        projection = build_goal_artifact_lifecycle_projection(
            goal_id=goal_id,
            goal=source,
            user_todo_summary=_mapping(
                attention.get("user_todos") or asset.get("user_todos")
            ),
            agent_todo_summary=_mapping(
                attention.get("agent_todos") or asset.get("agent_todos")
            ),
            run_history=source,
            work_lane_contract=_mapping(
                attention.get("work_lane_contract") or asset.get("work_lane_contract")
                or source.get("work_lane_contract")
            ),
            acceptance_gaps=frontier.get("acceptance_gaps") if "acceptance_gaps" in frontier else None,
            attention_item=attention,
        )
        record["artifact_lifecycle"] = projection


__all__ = [
    "GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION",
    "GUARD_KIND_EVIDENCE",
    "GUARD_KIND_OWNER_DECISION",
    "PHASE_CLOSED",
    "PHASE_CLOSING",
    "PHASE_QUALIFYING",
    "PHASE_STARTING",
    "PHASE_WAITING_OWNER",
    "attach_goal_artifact_lifecycle_projections",
    "build_goal_artifact_lifecycle_projection",
]
