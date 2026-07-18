from __future__ import annotations

from copy import deepcopy

from loopx.presentation.renderers.quota_markdown import (
    render_quota_markdown as render_quota_markdown_direct,
    render_quota_scheduler_ack_markdown as render_quota_scheduler_ack_markdown_direct,
    render_quota_should_run_markdown as render_quota_should_run_markdown_direct,
)
from loopx.quota import (
    render_quota_markdown,
    render_quota_scheduler_ack_markdown,
    render_quota_should_run_markdown,
)


def test_public_quota_renderers_are_presentation_exports() -> None:
    assert render_quota_markdown is render_quota_markdown_direct
    assert render_quota_should_run_markdown is render_quota_should_run_markdown_direct
    assert render_quota_scheduler_ack_markdown is render_quota_scheduler_ack_markdown_direct


def test_quota_rendering_preserves_the_decision_payload() -> None:
    payload = {
        "ok": True,
        "goal_id": "presentation-boundary",
        "decision": "run",
        "should_run": True,
        "interaction_contract": {
            "mode": "bounded_delivery",
            "agent_channel": {"must_attempt": True},
        },
        "quota": {"compute": "medium", "slot_minutes": 15},
    }
    original = deepcopy(payload)

    markdown = render_quota_should_run_markdown(payload)

    assert "# LoopX Quota Should Run" in markdown
    assert "- decision: `run`" in markdown
    assert payload == original
