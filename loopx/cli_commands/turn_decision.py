"""One shared fresh Turn decision for every Turn subcommand that needs one.

``run-once`` and ``managed-step`` must agree on what "the current governing
decision" means: read the same live status, apply the same controller advisory
primary, and sign the same ``loopx_turn_envelope_v0``. Duplicating that chain
would let the two drift, so both owners build through this module.

Nothing here executes, writes, or spends: it only projects the control plane's
current decision into the envelope the loop controller consumes.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..capabilities.explore.composition_frontier import (
    project_live_explore_composition_frontier,
)
from ..capabilities.periodic_report.pending_intent import (
    periodic_report_pending_intent_interaction_hook,
)
from ..control_plane.quota.live_decision import build_live_quota_should_run_decision
from ..control_plane.quota.turn_envelope import build_turn_envelope
from ..control_plane.scheduler.execution_context import (
    scheduler_execution_context_for_turn,
)
from ..status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, collect_status
from .lark_inbox import build_lark_operator_inbox_urgency_projector
from .turn_selection import turn_controller_advisory_primary

#: The route source every Turn owner attributes its decision to.
TURN_DECISION_ROUTE_SOURCE = "loopx_turn_plan"


def collect_turn_status_payload(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
) -> dict[str, Any]:
    """Read the live status the Turn decision is derived from."""

    scan_roots = [Path(item).expanduser() for item in args.scan_path]
    if not scan_roots:
        scan_roots = [Path(args.scan_root).expanduser()]
    return collect_status(
        registry_path=registry_path,
        runtime_root_override=runtime_root_arg,
        scan_roots=scan_roots,
        limit=max(max(0, args.limit), AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK),
        goal_id=args.goal_id,
        available_capabilities=args.available_capabilities,
    )


def turn_scheduler_execution_context(args: argparse.Namespace) -> Any:
    """The scheduler context every Turn owner signs its decision with."""

    return scheduler_execution_context_for_turn(
        host=args.host,
        execution_mode=args.execution_mode,
        scheduler_owner=args.scheduler_owner,
    )


def build_turn_decision_builder(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root: Path,
    runtime_root_arg: str | None,
    status_payload: Mapping[str, Any],
    turn_start_hook_dispatch: Mapping[str, Any] | None = None,
) -> Callable[..., dict[str, Any]]:
    """Return the shared ``build_turn_decision`` used by the Turn owners.

    ``turn_start_hook_dispatch`` is the caller's business: an executing Turn
    may publish Go/No-Go hooks before deciding, while a read-only managed step
    must not. Passing the projection in keeps that choice with the caller.
    """

    scheduler_context = turn_scheduler_execution_context(args)
    # Use the resolved runtime root, not the raw CLI argument. When a registry
    # declares `common_runtime_root` and the command omits `--runtime-root`,
    # the raw value is None and the activation check would silently read the
    # global default instead of this registry's own extension state.
    operator_inbox_urgency_projector = build_lark_operator_inbox_urgency_projector(
        runtime_root_arg=runtime_root,
    )

    def build_turn_decision(
        *, requested_action_todo_id: str | None = None
    ) -> dict[str, Any]:
        return build_live_quota_should_run_decision(
            status_payload,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            available_capabilities=args.available_capabilities,
            include_scheduler_detail=False,
            codex_app_current_rrule=None,
            registry_path=registry_path,
            runtime_root=runtime_root,
            route_source=TURN_DECISION_ROUTE_SOURCE,
            scheduler_execution_context=scheduler_context,
            operator_inbox_urgency_projector=operator_inbox_urgency_projector,
            bounded_research_frontier_projector=(
                project_live_explore_composition_frontier
            ),
            requested_action_todo_id=requested_action_todo_id,
            turn_start_hook_dispatch=dict(turn_start_hook_dispatch or {}),
            interaction_projection_hooks=(
                periodic_report_pending_intent_interaction_hook(
                    registry_path=registry_path,
                    runtime_root=runtime_root,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                ),
            ),
        )

    return build_turn_decision


def apply_controller_advisory_primary(
    build_turn_decision: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Build the decision, preferring the controller's advisory primary Todo."""

    decision = build_turn_decision()
    controller_default = turn_controller_advisory_primary(decision)
    if controller_default is None:
        return decision
    primary_todo_id, advisory_portfolio = controller_default
    decision = build_turn_decision(requested_action_todo_id=primary_todo_id)
    selected_todo = decision.get("selected_todo")
    if not isinstance(selected_todo, dict) or (
        selected_todo.get("todo_id") != primary_todo_id
    ):
        raise ValueError(
            "Turn controller advisory primary failed current eligibility"
        )
    selected_todo["selected_by"] = "turn_controller_advisory_primary"
    decision["action_portfolio"] = advisory_portfolio
    return decision


def fresh_turn_envelope(
    decision: Mapping[str, Any],
    *,
    scheduler_execution_context: Any,
) -> dict[str, Any]:
    """Sign the decision into the envelope the loop controller consumes.

    The causal link to a failed predecessor is *not* written here: the envelope
    schema is a signed contract, so the managed step passes its predecessor
    beside the envelope instead of mutating it.
    """

    return build_turn_envelope(
        decision,
        scheduler_execution_context=scheduler_execution_context,
    )


@dataclass(frozen=True)
class FreshTurnDecision:
    """The governing decision and the envelope signed from that same decision.

    Both halves are returned together so an owner that needs the raw decision
    besides the envelope - ``run-once`` reads it for reward recall - cannot
    re-derive its own copy and drift from what was signed.
    """

    decision: Mapping[str, Any]
    envelope: dict[str, Any]


def build_fresh_turn_decision(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root: Path,
    runtime_root_arg: str | None,
    turn_start_hook_dispatch: Mapping[str, Any] | None = None,
) -> FreshTurnDecision:
    """Resolve the current governing decision and sign it into an envelope.

    Every Turn owner goes through this one chain, so an added decision input is
    either visible to all of them or to none. `turn_start_hook_dispatch` is the
    caller's business: an executing Turn may publish Go/No-Go hooks before
    deciding, while a read-only step must not.
    """

    status_payload = collect_turn_status_payload(
        args,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
    )
    build_turn_decision = build_turn_decision_builder(
        args,
        registry_path=registry_path,
        runtime_root=runtime_root,
        runtime_root_arg=runtime_root_arg,
        status_payload=status_payload,
        turn_start_hook_dispatch=turn_start_hook_dispatch,
    )
    decision = apply_controller_advisory_primary(build_turn_decision)
    return FreshTurnDecision(
        decision=decision,
        envelope=fresh_turn_envelope(
            decision,
            scheduler_execution_context=turn_scheduler_execution_context(args),
        ),
    )


def build_fresh_envelope_for_managed_step(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root: Path,
    runtime_root_arg: str | None,
) -> dict[str, Any]:
    """Project the current decision as the managed step's fresh envelope.

    Read-only: no Turn-start hooks are dispatched and no Turn instance is
    minted, because the managed step only decides whether the outer scheduler
    may wake the same failed Turn again.
    """

    return build_fresh_turn_decision(
        args,
        registry_path=registry_path,
        runtime_root=runtime_root,
        runtime_root_arg=runtime_root_arg,
    ).envelope


__all__ = [
    "FreshTurnDecision",
    "TURN_DECISION_ROUTE_SOURCE",
    "apply_controller_advisory_primary",
    "build_fresh_envelope_for_managed_step",
    "build_fresh_turn_decision",
    "build_turn_decision_builder",
    "collect_turn_status_payload",
    "fresh_turn_envelope",
    "turn_scheduler_execution_context",
]
