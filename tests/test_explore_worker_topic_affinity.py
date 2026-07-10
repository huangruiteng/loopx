from __future__ import annotations

from loopx.capabilities.explore.worker_branch_plan import _affinity_key


def test_topic_affinity_uses_first_meaningful_token() -> None:
    assert (
        _affinity_key({"text": "[P0] Audit current result graph and evidence closure"})
        == "topic:result"
    )
    assert (
        _affinity_key({"text": "[P1] Review recent candidates against matched comparators"})
        == "topic:candidates"
    )
    assert (
        _affinity_key({"text": "[P2] Inspect latest planner implementation and deliver reusable fix"})
        == "topic:planner"
    )


def test_topic_affinity_does_not_emit_control_vocabulary() -> None:
    assert _affinity_key({"text": "[P0] Continue and update this todo"}) == "topic:general"


def test_explicit_affinity_signals_still_take_precedence() -> None:
    assert (
        _affinity_key(
            {
                "text": "[P0] Review candidate behavior",
                "required_write_scopes": ["loopx/capabilities/explore/**"],
                "required_capabilities": ["analysis"],
            }
        )
        == "scope:loopx/capabilities"
    )
    assert (
        _affinity_key(
            {
                "text": "[P0] Review candidate behavior",
                "required_capabilities": ["analysis"],
            }
        )
        == "capability:analysis"
    )
