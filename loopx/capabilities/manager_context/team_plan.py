"""The steward channel's host side of the team plan contract.

Two things about a team plan belong to the host rather than to the segment that
wrote the answer, and both live here so the channel reads one contract instead of
two:

* **The facts a preview is validated against.** A plan names the Goal it staffs
  and the manager channel is not bound to one Goal, so admission receives a
  per-Goal lookup rather than one Goal's Agents.
* **The hand-off to a confirmation surface.** The manager channel admits a
  preview when the segment that parsed the answer carried one, but admission only
  decides whether a preview may be *shown*; the product surfaces list typed
  actions, so an admitted preview still has to be handed to the owner of that
  surface before the owner can confirm it.

Nothing here creates work. The projected card is a preview: the owner's
confirmation applies it, and the apply re-validates the same payload with the
host's own facts. A projection that cannot be stored never fails the answer --
the owner keeps a correct answer and the gap becomes a typed Turn event --
because the surface that lists cards is not the authority that produced the
answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from ...agent_registry import load_goal_from_registry, registered_agent_ids_for_goal
from ...chat_manager import is_manager_channel
from ...control_plane.todos.contract import TODO_ACTION_KIND_ADVANCEMENT_VALUES
from ...control_plane.work_items.governed_transition_proposal import (
    STEWARD_TEAM_PLAN_PREVIEW_KIND,
)


def team_plan_admission_context(
    *,
    registry_path: Path | str | None,
    session: Mapping[str, Any],
    manager_scope_resolver: (
        Callable[[Mapping[str, Any]], list[str] | None] | None
    ) = None,
) -> dict[str, Any] | None:
    """Host facts a team preview may be validated against, per Goal.

    A team plan names its own Goal and the manager channel is not bound to one,
    so admission receives a lookup instead of one Goal's facts. The lookup
    re-uses the authorization the Turn owner already resolved: an external
    manager channel resolves only its authorized Goals, and a plan for any other
    Goal is dropped rather than validated against the Agents of a Goal it does
    not name. A host with no registry at all cannot describe any Goal, so its
    lookup answers ``None`` for every Goal instead of raising on a missing path.
    """

    channel_id = str(session.get("channel_id") or "")
    if not is_manager_channel(channel_id):
        return None

    def resolve(goal_id: str) -> list[str] | None:
        if not goal_id or registry_path is None:
            return None
        if channel_id != "manager":
            # The owner's own channel is not scoped to a subset of Goals;
            # an external channel only ever sees the Goals it was bound to.
            scope = manager_scope_resolver(session) if manager_scope_resolver else None
            if not isinstance(scope, list) or goal_id not in {
                str(item) for item in scope
            }:
                return None
        try:
            goal = load_goal_from_registry(Path(registry_path), goal_id)
        except (OSError, ValueError, TypeError, KeyError):
            return None
        if goal is None:
            # A Goal the registry does not know cannot be validated against
            # anything, and its lanes are not gaps: the plan is dropped.
            return None
        return registered_agent_ids_for_goal(goal)

    return {
        "resolve_registered_agents": resolve,
        "supported_action_kinds": sorted(TODO_ACTION_KIND_ADVANCEMENT_VALUES),
    }


class TeamPlanProjector(Protocol):
    """The surface owner's one operation: store an admitted preview as a card."""

    def __call__(self, preview: Mapping[str, Any]) -> Mapping[str, Any]: ...


class TurnEventSink(Protocol):
    """The Turn log a projection reports itself into."""

    def append_event(
        self,
        session_id: str,
        turn_id: str,
        *,
        kind: str,
        payload: dict[str, Any],
    ) -> Any: ...


def project_team_plan_preview(
    *,
    store: TurnEventSink,
    session: Mapping[str, Any],
    session_id: str,
    turn_id: str,
    response: Mapping[str, Any],
    projector: TeamPlanProjector | None,
) -> None:
    """Offer each admitted team preview in this answer as a confirmable card.

    Only the owner's own local manager channel is projected. A remote audience's
    confirmation surface is not this store, so its answer keeps the preview in
    text and no card is written on its behalf.
    """

    if projector is None or str(session.get("channel_id") or "") != "manager":
        return
    for proposal in response.get("proposals") or []:
        if (
            not isinstance(proposal, Mapping)
            or str(proposal.get("kind") or "") != STEWARD_TEAM_PLAN_PREVIEW_KIND
        ):
            continue
        preview = proposal.get("preview")
        if not isinstance(preview, Mapping):
            continue
        try:
            projected = projector(preview)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            store.append_event(
                session_id,
                turn_id,
                kind="team_plan.projection_failed",
                payload={
                    "error_code": "team_plan_projection_failed",
                    "message": str(exc)[:300],
                },
            )
            continue
        store.append_event(
            session_id,
            turn_id,
            kind="team_plan.projected",
            payload={
                "goal_id": str(preview.get("goal_id") or ""),
                "proposal_id": str(projected.get("proposal_id") or ""),
            },
        )


__all__ = [
    "TeamPlanProjector",
    "TurnEventSink",
    "project_team_plan_preview",
    "team_plan_admission_context",
]
