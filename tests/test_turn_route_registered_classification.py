"""The registered action domain must be classified explicitly and in full.

``_typed_route`` used to reach its ordinary verdict by subtraction: whatever
no branch matched became host execution. That makes a newly registered action
inherit a route nobody chose for it. The classification table states every
value the registered union can carry, and this module fails when an owner
gains a value the table does not name.

It also pins that the legacy/unknown path is unchanged. Narrowing what the
driver accepts is an admission-domain change with its own approval; this
change must not smuggle one in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loopx.control_plane.quota.effective_action import EffectiveAction
from loopx.control_plane.quota.turn_envelope import build_turn_envelope
from loopx.control_plane.turn_driver.driver import (
    REGISTERED_ACTION_ROUTES,
    REPLAN_ACTIONS,
    LoopXTurnRoute,
    _typed_route,
    compatibility_route,
)

REGISTRY = Path(__file__).resolve().parents[1] / "loopx" / "semantics" / "vocabulary_v0.json"
# The owner branch that validates its own projection before classifying, so it
# is a branch rather than a table entry.
VALIDATING_ACTION = EffectiveAction.GOVERNED_CAPABILITY_INTENT.value


def _registered_union() -> set[str]:
    """Every value the root should-run/Envelope action slot may carry."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    shared = registry["relations"]["shared_field_names"]
    names: set[str] = set()
    for entry in shared:
        if entry["field"] != "effective_action":
            continue
        for slot in entry["slots"]:
            for vocabulary in slot["vocabularies"]:
                names |= {
                    value if isinstance(value, str) else value["value"]
                    for value in registry["vocabularies"][vocabulary]["values"]
                }
    assert names, "expected the registry to describe the action slot union"
    return names


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


def test_every_registered_action_has_a_stated_classification() -> None:
    """A new owner value must be classified deliberately, not by subtraction."""
    classified = set(REGISTERED_ACTION_ROUTES) | {VALIDATING_ACTION}
    missing = sorted(_registered_union() - classified)
    assert not missing, (
        f"these registered actions have no stated route: {missing}. Add them to "
        "REGISTERED_ACTION_ROUTES rather than letting the compatibility path "
        "decide for them."
    )


def test_the_table_classifies_nothing_outside_the_registered_union() -> None:
    stale = sorted(set(REGISTERED_ACTION_ROUTES) - _registered_union())
    assert not stale, f"table names actions no owner carries: {stale}"


def test_the_validating_action_is_not_a_table_entry() -> None:
    """It checks its intent projection first, so it cannot be a lookup."""
    assert VALIDATING_ACTION not in REGISTERED_ACTION_ROUTES


@pytest.mark.parametrize("action", sorted(REGISTERED_ACTION_ROUTES))
def test_each_stated_classification_is_the_route_the_driver_takes(action: str) -> None:
    envelope = build_turn_envelope(_run_decision(effective_action=action))
    assert _typed_route(envelope) is REGISTERED_ACTION_ROUTES[action]


def test_replan_actions_keep_their_precedence_over_the_table() -> None:
    for action in sorted(REPLAN_ACTIONS):
        envelope = build_turn_envelope(_run_decision(effective_action=action))
        assert _typed_route(envelope) is LoopXTurnRoute.REPLAN_REQUIRED, action


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("legacy_workspace_repair", LoopXTurnRoute.REPAIR_REQUIRED),
        ("some_future_repair_required", LoopXTurnRoute.REPAIR_REQUIRED),
        ("an_action_nobody_registered", LoopXTurnRoute.READY_FOR_HOST),
        ("", LoopXTurnRoute.READY_FOR_HOST),
    ],
)
def test_unregistered_actions_keep_their_previous_verdict(
    action: str, expected: LoopXTurnRoute
) -> None:
    """Legacy and unknown values are still accepted, exactly as before."""
    assert compatibility_route(action) is expected
    envelope = build_turn_envelope(_run_decision(effective_action=action))
    assert _typed_route(envelope) is expected


def test_a_blocked_channel_still_precedes_any_classification() -> None:
    """Delivery and must-attempt are checked before the action is classified."""
    for action in ("normal_run", "control_plane_repair", "an_action_nobody_registered"):
        decision = _run_decision(effective_action=action)
        decision["interaction_contract"]["agent_channel"]["delivery_allowed"] = False
        assert _typed_route(build_turn_envelope(decision)) is LoopXTurnRoute.BLOCKED, action
