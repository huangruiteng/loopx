"""Characterisation of how ``_typed_route`` classifies each registered action.

The driver used to carry a literal ``REPAIR_ACTIONS`` set beside the
``_repair``/``_repair_required`` suffix rule. Every value in that set already
ended in ``_repair``, and none of them was ever an ``EffectiveAction`` member,
so the set could never decide a route the suffix did not already decide. This
module pins the resulting classification so a future edit cannot reintroduce an
unreachable set, or silently change which actions reach the repair route.
"""

from __future__ import annotations

from typing import Any

from loopx.control_plane.quota.effective_action import EffectiveAction
from loopx.control_plane.quota.turn_envelope import build_turn_envelope
from loopx.control_plane.turn_driver.driver import REPLAN_ACTIONS, _typed_route

# The literal values the removed ``REPAIR_ACTIONS`` set carried. They are kept
# here as inputs, not as a classification source: the suffix rule alone has to
# keep routing them, which is why removing the set preserved behaviour.
RETIRED_REPAIR_ACTION_SET = (
    "capability_repair",
    "projection_repair",
    "self_repair",
    "state_projection_repair",
    "workspace_repair",
)


def _run_decision(**overrides: Any) -> dict[str, Any]:
    decision: dict[str, Any] = {
        "ok": True,
        "goal_id": "g",
        "agent_id": "a",
        "agent_identity": {"agent_id": "a"},
        "decision": "run",
        "should_run": True,
        "effective_action": "normal_run",
        "state": "eligible",
        "recommended_action": "Advance.",
        "selected_todo": {"todo_id": "t001", "text": "Advance."},
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "normal_run",
            "user_channel": {"action_required": False, "notify": "DONT_NOTIFY"},
            "agent_channel": {
                "must_attempt": True,
                "delivery_allowed": True,
                "quiet_noop_allowed": False,
            },
            "cli_channel": {"spend_after_validation": True},
        },
        "open_count": 0,
        "action_required": False,
    }
    decision.update(overrides)
    return decision


def _route_for(action: str) -> str:
    return _typed_route(build_turn_envelope(_run_decision(effective_action=action))).value


def test_every_repair_suffixed_action_reaches_the_repair_route() -> None:
    suffixed = sorted(
        value
        for value in (member.value for member in EffectiveAction)
        if value.endswith(("_repair", "_repair_required"))
    )
    assert suffixed, "expected registered repair actions to exist"
    for action in suffixed:
        assert _route_for(action) == "repair_required", action


def test_retired_repair_set_still_routes_through_the_suffix_rule() -> None:
    # Removing the literal set must not change how these strings classify.
    for action in RETIRED_REPAIR_ACTION_SET:
        assert action.endswith("_repair"), action
        assert _route_for(action) == "repair_required", action


def test_retired_repair_set_was_never_a_registered_action() -> None:
    registered = {member.value for member in EffectiveAction}
    for action in RETIRED_REPAIR_ACTION_SET:
        assert action not in registered, action


def test_replan_actions_reach_the_replan_route() -> None:
    for action in sorted(REPLAN_ACTIONS):
        assert _route_for(action) == "replan_required", action


def test_remaining_registered_actions_reach_the_host_route() -> None:
    special = (
        {value for value in REPLAN_ACTIONS}
        | {EffectiveAction.GOVERNED_CAPABILITY_INTENT.value}
    )
    for member in EffectiveAction:
        action = member.value
        if action in special or action.endswith(("_repair", "_repair_required")):
            continue
        assert _route_for(action) == "ready_for_host", action
