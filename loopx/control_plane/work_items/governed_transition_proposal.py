"""Materialize governed provider proposals through LoopX-owned Todo APIs."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from enum import StrEnum
from pathlib import Path
from typing import Any

from ...todos import (
    add_goal_todo,
    complete_goal_todo,
    list_goal_todos,
    update_goal_todo,
)
from ..runtime.public_safety import validate_public_safe_value
from ..todos.contract import (
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_capability_binding_ref,
)

GOVERNED_TRANSITION_RECEIPT_SCHEMA_VERSION = (
    "loopx_governed_transition_proposal_receipt_v0"
)
_RECEIPT_FIELDS = {
    "schema_version",
    "proposal_id",
    "proposal_digest",
    "kind",
    "monitor_key",
    "action",
    "todo_id",
    "status",
    "target_key",
}
# Receipts are persisted in the settlement journal, so the field set stays
# closed and a new field is admitted only as an explicitly bounded addition
# that an older receipt may still omit. `lane_todo_ids` is the readback of a
# team plan: every lane Todo the settlement ensured, not just the first one.
_OPTIONAL_RECEIPT_FIELDS = {"lane_todo_ids", "intent_basis"}
_LANE_TODO_ID_LIMIT = 8
_LANE_TODO_ID = re.compile(r"^todo_[A-Za-z0-9]{1,40}$")
_INTENT_BASIS = re.compile(r"^sha256:[0-9a-f]{64}$")


TransitionCheckpoint = Callable[[list[dict[str, Any]]], None]


class GovernedTransitionSettlementPhase(StrEnum):
    """Turn-settlement phase that owns one admitted Kernel transition."""

    PRE_SETTLEMENT = "pre_settlement"
    POST_SETTLEMENT = "post_settlement"


STEWARD_TEAM_PLAN_PREVIEW_KIND = "steward_team_plan_preview"

_SETTLEMENT_PHASE_BY_PROPOSAL_KIND = {
    "continuous_monitor_upsert": GovernedTransitionSettlementPhase.PRE_SETTLEMENT,
    "continuous_monitor_complete": GovernedTransitionSettlementPhase.POST_SETTLEMENT,
    STEWARD_TEAM_PLAN_PREVIEW_KIND: GovernedTransitionSettlementPhase.PRE_SETTLEMENT,
}


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): deepcopy(item) for key, item in value.items()}


def validate_governed_transition_receipts(
    value: object,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError(
            "governed transition proposal receipts must contain at most 64 items"
        )
    receipts: list[dict[str, Any]] = []
    proposal_ids: set[str] = set()
    for index, raw in enumerate(value):
        receipt = _mapping(raw, f"governed transition receipt[{index}]")
        # An older receipt may omit the bounded readback field; nothing else may
        # be added, so a receipt can never carry a field it did not mean to.
        if not _RECEIPT_FIELDS <= set(receipt) <= (
            _RECEIPT_FIELDS | _OPTIONAL_RECEIPT_FIELDS
        ):
            raise ValueError("governed transition proposal receipt fields are invalid")
        if receipt.get("schema_version") != GOVERNED_TRANSITION_RECEIPT_SCHEMA_VERSION:
            raise ValueError("governed transition proposal receipt schema is invalid")
        proposal_id = str(receipt.get("proposal_id") or "")
        if not proposal_id or proposal_id in proposal_ids:
            raise ValueError("governed transition proposal receipt identity is invalid")
        proposal_ids.add(proposal_id)
        if receipt.get("kind") not in {
            "continuous_monitor_upsert",
            "continuous_monitor_complete",
            STEWARD_TEAM_PLAN_PREVIEW_KIND,
        }:
            raise ValueError("governed transition proposal receipt kind is invalid")
        if receipt.get("status") != "committed":
            raise ValueError("governed transition proposal receipt status is invalid")
        for field in ("proposal_digest", "action", "todo_id"):
            if not isinstance(receipt.get(field), str) or not receipt[field]:
                raise ValueError(
                    f"governed transition proposal receipt {field} is invalid"
                )
        # A monitor transition is identified by its monitor key, so that key is
        # required there. A team plan is not a monitor and must not invent one,
        # so its key is explicitly absent rather than an empty string.
        monitor_key = receipt.get("monitor_key")
        if receipt.get("kind") == STEWARD_TEAM_PLAN_PREVIEW_KIND:
            if monitor_key is not None:
                raise ValueError(
                    "governed transition proposal receipt monitor_key is invalid"
                )
        elif not isinstance(monitor_key, str) or not monitor_key:
            raise ValueError(
                "governed transition proposal receipt monitor_key is invalid"
            )
        if receipt.get("target_key") is not None and not isinstance(
            receipt.get("target_key"), str
        ):
            raise ValueError(
                "governed transition proposal receipt target_key is invalid"
            )
        lane_todo_ids = receipt.get("lane_todo_ids")
        if lane_todo_ids is not None and (
            not isinstance(lane_todo_ids, list)
            or not 1 <= len(lane_todo_ids) <= _LANE_TODO_ID_LIMIT
            or len(set(lane_todo_ids)) != len(lane_todo_ids)
            or any(
                not isinstance(item, str) or not _LANE_TODO_ID.fullmatch(item)
                for item in lane_todo_ids
            )
        ):
            raise ValueError(
                "governed transition proposal receipt lane_todo_ids is invalid"
            )
        intent_basis = receipt.get("intent_basis")
        if intent_basis is not None and (
            not isinstance(intent_basis, str)
            or not _INTENT_BASIS.fullmatch(intent_basis)
        ):
            raise ValueError(
                "governed transition proposal receipt intent_basis is invalid"
            )
        validate_public_safe_value(receipt, path=f"transition_receipts[{index}]")
        receipts.append(receipt)
    return receipts


def _monitor_for_key(
    *,
    registry_path: Path,
    goal_id: str,
    monitor_key: str,
) -> dict[str, Any] | None:
    projection = list_goal_todos(
        registry_path=registry_path,
        goal_id=goal_id,
        role="agent",
    )
    matches = [
        item
        for item in projection.get("todos", [])
        if isinstance(item, dict)
        and normalize_todo_capability_binding_ref(item.get("capability_binding_ref"))
        == monitor_key
    ]
    if len(matches) > 1:
        raise ValueError("governed monitor proposal matched multiple Todos")
    if not matches:
        return None
    item = matches[0]
    if item.get("task_class") != TODO_TASK_CLASS_MONITOR:
        raise ValueError("governed monitor proposal matched a non-monitor Todo")
    return item


def _upsert_monitor(
    *,
    registry_path: Path,
    goal_id: str,
    agent_id: str,
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    monitor_key = str(proposal["monitor_key"])
    current = _monitor_for_key(
        registry_path=registry_path,
        goal_id=goal_id,
        monitor_key=monitor_key,
    )
    monitor_metadata = {
        "target_key": str(proposal["target_key"]),
        "cadence": str(proposal["cadence"]),
        "next_due_at": str(proposal["next_due_at"]),
        "expires_at": str(proposal["expires_at"]),
    }
    if current is None:
        result = add_goal_todo(
            registry_path=registry_path,
            goal_id=goal_id,
            role="agent",
            text=str(proposal["text"]),
            status=TODO_STATUS_OPEN,
            task_class=TODO_TASK_CLASS_MONITOR,
            action_kind=str(proposal["action_kind"]),
            capability_binding_ref=monitor_key,
            required_capabilities=[
                str(item) for item in proposal["required_capabilities"]
            ],
            claimed_by=agent_id,
            agent_id=agent_id,
            monitor_metadata=monitor_metadata,
        )
        action = "created" if result.get("added") else "reused"
    else:
        if current.get("status") == TODO_STATUS_DONE:
            raise ValueError("governed monitor proposal cannot reopen a completed Todo")
        if current.get("status") != TODO_STATUS_OPEN:
            raise ValueError("governed monitor proposal requires an open monitor Todo")
        owner = str(current.get("claimed_by") or "")
        if owner and owner != agent_id:
            raise ValueError("governed monitor proposal cannot reassign another Agent")
        result = update_goal_todo(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=str(current["todo_id"]),
            role="agent",
            text=str(proposal["text"]),
            status=TODO_STATUS_OPEN,
            task_class=TODO_TASK_CLASS_MONITOR,
            action_kind=str(proposal["action_kind"]),
            required_capabilities=[
                str(item) for item in proposal["required_capabilities"]
            ],
            claimed_by=agent_id,
            agent_id=agent_id,
            monitor_metadata=monitor_metadata,
        )
        action = "updated" if result.get("changed") else "unchanged"
    return {
        "action": action,
        "todo_id": str(result["todo_id"]),
        "target_key": str(proposal["target_key"]),
    }


def _intent_basis_for(
    *,
    goal_id: str,
    goal: Mapping[str, Any],
    registry_path: Path,
    preview: Mapping[str, Any],
) -> str | None:
    """Read the canonical source basis one work-graph edit is applied against.

    The source basis is a Goal-level fact, so any of the Goal's Agents reads the
    same one; a ready lane is preferred because that is where the work will live.
    A Goal whose basis cannot be read omits the field rather than inventing one.
    """

    lanes = preview.get("lanes") or []
    basis_agent = next(
        (
            str(lane.get("agent_id"))
            for lane in lanes
            if lane.get("staffing") == "ready"
        ),
        str(lanes[0].get("agent_id")) if lanes else "",
    )
    if not basis_agent:
        return None
    try:
        from ...control_plane.goals.shared_goal_alignment import (
            project_shared_goal_alignment,
        )

        alignment = project_shared_goal_alignment(
            goal_id=goal_id,
            agent_id=basis_agent,
            project=Path(str(goal.get("repo") or ".")).expanduser(),
            registry_path=Path(registry_path),
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return None
    basis = (alignment.get("source_basis") or {}).get("source_basis_digest")
    return str(basis) if basis else None


def _apply_team_plan(
    *,
    registry_path: Path,
    goal_id: str,
    agent_id: str,
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the confirmed lanes' first bounded Todos through the Todo owner.

   The plan is re-validated here against this Goal's registered Agents and the
   shipped advancement action kinds, so a proposal cannot become work by
   bypassing admission. Only lanes the preview already marked ready are
   materialized; a lane the preview reported as a gap stays a gap and creates
   nothing, and the canonical Todo owner decides whether a row is added or
   reused, which makes a replayed settlement idempotent.
   """

    from ...agent_registry import registered_agent_ids_for_goal
    from ...history import load_registry
    from ...registry import registry_goals
    from ..todos.contract import TODO_ACTION_KIND_ADVANCEMENT_VALUES

    # The plan names the Goal it staffs, and it may not be retargeted by the
    # settlement it arrives in: admitting a plan against one Goal's agents and
    # then creating its lanes under another would be a silent widening.
    if str(proposal.get("goal_id") or "") != goal_id:
        raise ValueError(
            "steward team plan proposal names a different Goal than its settlement"
        )
    registry = load_registry(registry_path)
    goal = next(
        (
            item
            for item in registry_goals(registry)
            if str(item.get("id") or "") == goal_id
        ),
        None,
    )
    if goal is None:
        raise ValueError("steward team plan proposal names an unknown Goal")
    preview = validate_steward_team_plan_preview(
        proposal,
        registered_agent_ids=registered_agent_ids_for_goal(goal),
        supported_action_kinds=sorted(TODO_ACTION_KIND_ADVANCEMENT_VALUES),
    )
    # Traceability is read before the edit: the receipt names the canonical
    # basis this work-graph edit was applied against, so the lanes could not
    # make the basis describe their own creation. A Goal whose basis cannot be
    # read omits the field instead of inventing one.
    intent_basis = _intent_basis_for(goal_id=goal_id, goal=goal, registry_path=registry_path, preview=preview)
    created: list[str] = []
    reused: list[str] = []
    for lane in preview["lanes"]:
        if lane.get("staffing") != "ready":
            continue
        first_todo = lane["first_todo"]
        result = add_goal_todo(
            registry_path=Path(registry_path).expanduser(),
            goal_id=goal_id,
            role="agent",
            text=str(first_todo["text"]),
            status=TODO_STATUS_OPEN,
            task_class=TODO_TASK_CLASS_ADVANCEMENT,
            action_kind=str(first_todo["action_kind"]),
            claimed_by=str(lane["agent_id"]),
            agent_id=str(lane["agent_id"]),
        )
        if result.get("added"):
            created.append(str(result["todo_id"]))
        else:
            reused.append(str(result["todo_id"]))
    # The receipt names every lane Todo this settlement ensured, whether the
    # canonical owner added it or found it already present, so a replayed
    # settlement still reports the same identities instead of an empty one.
    lane_todo_ids = [*created, *reused]
    return {
        "action": "created" if created else "reused",
        "todo_id": lane_todo_ids[0] if lane_todo_ids else "",
        "target_key": None,
        "created_todo_ids": created,
        "lane_todo_ids": lane_todo_ids,
        "intent_basis": intent_basis,
        "reused_lane_count": len(reused),
        "gap_count": len(preview["gaps"]),
    }


def _complete_monitor(
    *,
    registry_path: Path,
    goal_id: str,
    agent_id: str,
    effect_id: str,
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    current = _monitor_for_key(
        registry_path=registry_path,
        goal_id=goal_id,
        monitor_key=str(proposal["monitor_key"]),
    )
    if current is None:
        raise ValueError("governed monitor completion has no materialized Todo")
    owner = str(current.get("claimed_by") or "")
    if owner and owner != agent_id:
        raise ValueError("governed monitor completion cannot mutate another Agent")
    completion_key = (
        "governed_transition_"
        + hashlib.sha256(f"{effect_id}:{proposal['proposal_id']}".encode()).hexdigest()[
            :32
        ]
    )
    result = complete_goal_todo(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=str(current["todo_id"]),
        role="agent",
        evidence=str(proposal["evidence"]),
        completion_turn_key=completion_key,
        no_followup=True,
        claimed_by=agent_id,
        agent_id=agent_id,
        authority_reason="validated governed external-capability proposal",
    )
    return {
        "action": ("replayed" if result.get("idempotent_replay") else "completed"),
        "todo_id": str(result["todo_id"]),
        "target_key": current.get("target_key"),
    }


def settle_governed_transition_proposals(
    *,
    registry_path: str | Path,
    goal_id: str,
    agent_id: str,
    effect_id: str,
    proposals: Sequence[Mapping[str, Any]],
    existing_receipts: object,
    checkpoint: TransitionCheckpoint,
    phase: GovernedTransitionSettlementPhase,
) -> list[dict[str, Any]]:
    """Apply admitted proposals for one settlement phase and checkpoint receipts."""

    receipts = validate_governed_transition_receipts(existing_receipts)
    by_proposal_id = {str(item["proposal_id"]): item for item in receipts}
    for raw in proposals:
        proposal = _mapping(raw, "governed transition proposal")
        kind = str(proposal.get("kind") or "")
        proposal_phase = _SETTLEMENT_PHASE_BY_PROPOSAL_KIND.get(kind)
        if proposal_phase is None:
            raise ValueError("governed transition proposal kind is unsupported")
        proposal_id = str(proposal.get("proposal_id") or "")
        proposal_digest = _canonical_digest(proposal)
        replay = by_proposal_id.get(proposal_id)
        if replay is not None:
            if (
                replay.get("proposal_digest") != proposal_digest
                or replay.get("kind") != proposal.get("kind")
                or replay.get("monitor_key") != proposal.get("monitor_key")
            ):
                raise ValueError(
                    "governed transition proposal replay does not match its receipt"
                )
            continue
        if proposal_phase is not phase:
            continue
        if kind == "continuous_monitor_upsert":
            result = _upsert_monitor(
                registry_path=Path(registry_path).expanduser(),
                goal_id=goal_id,
                agent_id=agent_id,
                proposal=proposal,
            )
        elif kind == STEWARD_TEAM_PLAN_PREVIEW_KIND:
            result = _apply_team_plan(
                registry_path=Path(registry_path),
                goal_id=goal_id,
                agent_id=agent_id,
                proposal=proposal,
            )
        elif kind == "continuous_monitor_complete":
            result = _complete_monitor(
                registry_path=Path(registry_path).expanduser(),
                goal_id=goal_id,
                agent_id=agent_id,
                effect_id=effect_id,
                proposal=proposal,
            )
        else:
            raise RuntimeError("governed transition proposal dispatch is incomplete")
        receipt = {
            "schema_version": GOVERNED_TRANSITION_RECEIPT_SCHEMA_VERSION,
            "proposal_id": proposal_id,
            "proposal_digest": proposal_digest,
            "kind": kind,
            "monitor_key": (
                str(proposal["monitor_key"])
                if proposal.get("monitor_key") is not None
                else None
            ),
            "action": str(result["action"]),
            "todo_id": str(result["todo_id"]),
            "status": "committed",
            "target_key": result.get("target_key"),
        }
        lane_todo_ids = result.get("lane_todo_ids")
        if lane_todo_ids:
            # The apply ensured every ready lane's first Todo; a receipt that
            # named only the first one could not be read as "what exists now".
            receipt["lane_todo_ids"] = [str(item) for item in lane_todo_ids]
        if result.get("intent_basis"):
            # The work-graph edit this receipt records is traceable to the
            # canonical basis it was applied against, so a lane Todo can be tied
            # back to the intent revision it was meant to advance.
            receipt["intent_basis"] = str(result["intent_basis"])
        validate_public_safe_value(receipt, path="transition_receipt")
        receipts.append(receipt)
        by_proposal_id[proposal_id] = receipt
        checkpoint(receipts)
    return receipts


STEWARD_TEAM_PLAN_PREVIEW_SCHEMA_VERSION = "steward_team_plan_preview_v0"
STEWARD_TEAM_PLAN_LANE_LIMIT = 8
STEWARD_TEAM_PLAN_PRIORITIES = ("P0", "P1", "P2", "P3")
_GOAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
# The reasons a plan may declare for a lane it cannot staff itself.
STEWARD_TEAM_PLAN_GAP_REASONS = (
    "agent_not_registered",
    "capability_not_granted",
    "audience_not_authorized",
)
# The reasons this host reports for a lane *it* cannot staff. They are the
# host's own verdict about the same lane fact, so they stay a separate
# vocabulary: a plan may not claim one of these to describe its own lane, and a
# reader can tell an owner-declared gap from a staffability verdict Core made.
STEWARD_TEAM_PLAN_UNSUPPORTED_ACTION_KIND = "action_kind_not_supported"
STEWARD_TEAM_PLAN_HOST_GAP_REASONS = (STEWARD_TEAM_PLAN_UNSUPPORTED_ACTION_KIND,)


def _plan_text(value: object, label: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError(f"{label} must be a non-empty string")
    if len(text) > 600:
        raise ValueError(f"{label} exceeds the public-safe preview length")
    validate_public_safe_value({"value": text}, path=label)
    return text


def _unstaffed_lane(
    *,
    lane_id: str,
    agent_id: str,
    acceptance: str,
    reason_code: str,
    first_todo: Mapping[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """One lane this host cannot staff, keeping the work it declined.

    A gap lane names the lane, the Agent it was asked to run on, the acceptance
    signal it was meant to end on, and the typed reason it is not staffed. It
    carries no ``first_todo``: the work it did not staff is evidence, not a lane
    that exists, and it is kept either as the declined first Todo or as the note
    the plan gave for the lane. One of the two is always present, so a reader can
    always see why the lane is a gap instead of finding an unexplained one.
    """

    lane = {
        "lane_id": lane_id,
        "agent_id": agent_id,
        "acceptance": acceptance,
        "staffing": "gap",
        "gap_reason_code": reason_code,
    }
    if first_todo is not None:
        lane["declined_first_todo"] = dict(first_todo)
    if note is not None:
        lane["gap_note"] = note
    return lane


def _declined_todo(value: object) -> dict[str, Any]:
    """Read the work a gap lane kept, without judging whether it can run.

    The work a lane declined is evidence of what the owner asked for, so it is
    bounded for public safety but not held to the staffability rules a lane that
    will actually run must pass: the whole reason it is kept is that this host
    could not staff it, and re-reading it must not turn an admitted gap back
    into work.
    """

    declined = _mapping(value, "declined_first_todo")
    priority = str(declined.get("priority") or "")
    if priority not in STEWARD_TEAM_PLAN_PRIORITIES:
        raise ValueError("declined_first_todo priority is invalid")
    task_class = str(declined.get("task_class") or "")
    if task_class != "advancement_task":
        raise ValueError(
            "a lane's declined first bounded Todo must be an advancement_task"
        )
    return {
        "text": _plan_text(declined.get("text"), "declined_first_todo text"),
        "priority": priority,
        "task_class": task_class,
        "action_kind": _plan_text(
            declined.get("action_kind"), "declined_first_todo action_kind"
        ),
    }


def validate_steward_team_plan_preview(
    payload: object,
    *,
    registered_agent_ids: Sequence[str],
    supported_action_kinds: Sequence[str],
) -> dict[str, Any]:
    """Validate one steward team preview, and refuse to invent its staffing.

    Validation is the same contract at both ends: the Chat admission uses it to
    decide whether a preview may be surfaced for confirmation, and the
    ``PRE_SETTLEMENT`` apply of that kind calls it again with the host's own
    facts before it creates anything, so a proposal cannot become work by
    bypassing admission. A lane whose Agent this Goal does not register becomes
    a typed gap that keeps the work it did *not* staff under
    ``declined_first_todo``, so the owner sees what was asked for and what is
    missing instead of a lane that was quietly filled in or dropped.

    The same holds for an action kind this host does not ship: it is a fact
    about one lane's staffability, not a malformed plan, so that lane becomes a
    typed gap and the plan is still admitted with its other lanes ready. Only a
    payload the host cannot read at all -- a wrong schema, an unstaffable
    plan-level field, or a lane that omits the Todo shape -- is refused whole.
    """

    plan = _mapping(payload, "steward_team_plan_preview")
    if plan.get("schema_version") != STEWARD_TEAM_PLAN_PREVIEW_SCHEMA_VERSION:
        raise ValueError("steward team plan preview schema_version is invalid")
    if plan.get("kind") != STEWARD_TEAM_PLAN_PREVIEW_KIND:
        raise ValueError("steward team plan preview kind is invalid")
    # The plan names the Goal it staffs. Without that, the admission that
    # validates its lanes and the settlement that materializes them would each
    # have to guess which Goal's agents the host should describe, and a plan
    # could be admitted against one Goal's facts and applied under another's.
    goal_id = _plan_text(plan.get("goal_id"), "goal_id")
    if not _GOAL_ID.fullmatch(goal_id):
        raise ValueError("steward team plan preview requires an exact Goal id")
    registered = {str(value) for value in registered_agent_ids}
    action_kinds = {str(value) for value in supported_action_kinds}
    lanes_value = plan.get("lanes")
    if not isinstance(lanes_value, Sequence) or isinstance(lanes_value, (str, bytes)):
        raise ValueError("steward team plan preview requires a lane list")
    if not 1 <= len(lanes_value) <= STEWARD_TEAM_PLAN_LANE_LIMIT:
        raise ValueError(
            f"steward team plan preview requires 1..{STEWARD_TEAM_PLAN_LANE_LIMIT} lanes"
        )
    lanes: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    seen_lanes: set[str] = set()
    for raw_lane in lanes_value:
        lane = _mapping(raw_lane, "steward_team_plan_lane")
        lane_id = _plan_text(lane.get("lane_id"), "lane_id")
        if lane_id in seen_lanes:
            raise ValueError("steward team plan preview repeats a lane_id")
        seen_lanes.add(lane_id)
        agent_id = _plan_text(lane.get("agent_id"), "agent_id")
        acceptance = _plan_text(lane.get("acceptance"), "lane acceptance")
        declared_gap = lane.get("staffing_gap")
        requested_todo = lane.get("first_todo")
        if declared_gap is not None:
            gap = _mapping(declared_gap, "staffing_gap")
            reason_code = str(gap.get("reason_code") or "")
            if reason_code not in STEWARD_TEAM_PLAN_GAP_REASONS:
                raise ValueError("staffing_gap reason_code is invalid")
            if requested_todo is not None:
                raise ValueError("a lane that declares a gap may not declare work")
            lanes.append(
                _unstaffed_lane(
                    lane_id=lane_id,
                    agent_id=agent_id,
                    acceptance=acceptance,
                    reason_code=reason_code,
                    note=_plan_text(gap.get("note"), "staffing_gap note"),
                )
            )
            gaps.append({"lane_id": lane_id, "reason_code": reason_code})
            continue
        if requested_todo is None:
            # A lane that arrives without work is a verdict somebody already
            # made: this host's own, when an admitted preview is re-read by the
            # apply, or the plan's, handled above. It is preserved rather than
            # re-derived, so validation is idempotent and an apply cannot staff a
            # lane the owner was shown as unstaffed.
            reason_code = str(lane.get("gap_reason_code") or "")
            if reason_code not in (
                STEWARD_TEAM_PLAN_GAP_REASONS + STEWARD_TEAM_PLAN_HOST_GAP_REASONS
            ):
                raise ValueError("lane gap_reason_code is invalid")
            declined = lane.get("declined_first_todo")
            note = lane.get("gap_note")
            if declined is None and note is None:
                raise ValueError("a lane without work must keep why it is a gap")
            lanes.append(
                _unstaffed_lane(
                    lane_id=lane_id,
                    agent_id=agent_id,
                    acceptance=acceptance,
                    reason_code=reason_code,
                    first_todo=(
                        _declined_todo(declined) if declined is not None else None
                    ),
                    note=(
                        _plan_text(note, "gap_note") if note is not None else None
                    ),
                )
            )
            gaps.append({"lane_id": lane_id, "reason_code": reason_code})
            continue
        first_todo = _mapping(requested_todo, "first_todo")
        text = _plan_text(first_todo.get("text"), "first_todo text")
        priority = str(first_todo.get("priority") or "")
        if priority not in STEWARD_TEAM_PLAN_PRIORITIES:
            raise ValueError("first_todo priority is invalid")
        task_class = str(first_todo.get("task_class") or "")
        if task_class != "advancement_task":
            raise ValueError("a lane's first bounded Todo must be an advancement_task")
        action_kind = str(first_todo.get("action_kind") or "")
        normalized_todo = {
            "text": text,
            "priority": priority,
            "task_class": task_class,
            "action_kind": action_kind,
        }
        # Two different host facts make one lane unstaffable: this Goal does not
        # register its Agent, or this host does not ship the action kind it asked
        # for. Both are staffability facts about *one* lane, so both become the
        # same typed gap and keep the declined work. Neither may refuse the plan:
        # a plan whose first lane cannot be staffed is still the owner's request,
        # and its staffable lanes are exactly what the owner asked to review.
        # Before this, an unsupported kind raised, so Chat admission dropped the
        # whole plan and the owner saw correct prose with nothing to confirm.
        if agent_id not in registered:
            lane_gap_reason = "agent_not_registered"
        elif action_kind not in action_kinds:
            lane_gap_reason = STEWARD_TEAM_PLAN_UNSUPPORTED_ACTION_KIND
        else:
            lane_gap_reason = ""
        if lane_gap_reason:
            lanes.append(
                _unstaffed_lane(
                    lane_id=lane_id,
                    agent_id=agent_id,
                    acceptance=acceptance,
                    reason_code=lane_gap_reason,
                    first_todo=normalized_todo,
                )
            )
            gaps.append({"lane_id": lane_id, "reason_code": lane_gap_reason})
            continue
        lanes.append(
            {
                "lane_id": lane_id,
                "agent_id": agent_id,
                "acceptance": acceptance,
                "staffing": "ready",
                "first_todo": normalized_todo,
            }
        )
    envelope = _mapping(plan.get("quota_envelope"), "quota_envelope")
    if not envelope:
        raise ValueError("steward team plan preview requires a quota envelope")
    validate_public_safe_value(envelope, path="quota_envelope")
    preview = {
        "schema_version": STEWARD_TEAM_PLAN_PREVIEW_SCHEMA_VERSION,
        "kind": STEWARD_TEAM_PLAN_PREVIEW_KIND,
        "goal_id": goal_id,
        "objective": _plan_text(plan.get("objective"), "objective"),
        "lanes": lanes,
        "gaps": gaps,
        "quota_envelope": dict(envelope),
        "stop_condition": _plan_text(plan.get("stop_condition"), "stop_condition"),
        # A preview is never an effect: the contract states it, so a reader does
        # not have to know which materializers happen to be registered.
        "applies": False,
    }
    validate_public_safe_value(preview, path="steward_team_plan_preview")
    return preview
