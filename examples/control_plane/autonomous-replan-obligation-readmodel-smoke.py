#!/usr/bin/env python3
"""Smoke-test autonomous replan obligation builder read-model parity."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.autonomous_replan_obligation import (  # noqa: E402
    autonomous_replan_obligation_from_state as direct_autonomous_replan_obligation_from_state,
    build_autonomous_replan_obligation as direct_build_autonomous_replan_obligation,
    build_autonomous_replan_obligation_payload,
)
from loopx.status import (  # noqa: E402
    AUTONOMOUS_REPLAN_SECTION_HEADINGS,
    AUTONOMOUS_REPLAN_SCHEMA_VERSION,
    AUTONOMOUS_REPLAN_STALL_THRESHOLD,
    DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
    DEAD_MONITOR_REPEAT_THRESHOLD,
    active_state_section_entries,
    active_state_sections,
    autonomous_replan_obligation,
    build_autonomous_replan_obligation,
    public_safe_compact_text,
)


AGENT_TODOS = {
    "first_open_items": [
        {
            "priority": "P2",
            "text": "[P2] Continue canary-gated control-plane read-model cleanup.",
            "claimed_by": "codex-control-plane",
        }
    ]
}

STATE_TEXT = """# Goal

## Next Action

- Continue until no-progress streak is resolved.

## Operating Lessons

- Record mitigation when repeated action loop appears.
- Keep a periodic review every few dozen runs.
"""


def direct(evidence: list[dict[str, object]]) -> dict[str, object] | None:
    return direct_build_autonomous_replan_obligation(
        evidence,
        agent_todos=AGENT_TODOS,
        public_safe_compact_text=public_safe_compact_text,
        autonomous_replan_schema_version=AUTONOMOUS_REPLAN_SCHEMA_VERSION,
        autonomous_replan_stall_threshold=AUTONOMOUS_REPLAN_STALL_THRESHOLD,
        dead_monitor_repeat_threshold=DEAD_MONITOR_REPEAT_THRESHOLD,
        dead_monitor_repeat_schema_version=DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
    )


def assert_parity(evidence: list[dict[str, object]]) -> dict[str, object]:
    wrapper = build_autonomous_replan_obligation(evidence, agent_todos=AGENT_TODOS)
    direct_result = direct(evidence)
    assert wrapper == direct_result, (wrapper, direct_result)
    assert wrapper is not None, wrapper
    return wrapper


def assert_payload_builder_contract() -> None:
    payload = build_autonomous_replan_obligation_payload(
        schema_version=AUTONOMOUS_REPLAN_SCHEMA_VERSION,
        agent_id="codex-product-capability",
        stall_threshold=1,
        trigger_count=1,
        triggers=[
            {
                "kind": "vision_acceptance_gap",
                "section": "goal_frontier_projection.acceptance_gaps",
                "text": "active agent vision remains open",
            }
        ],
        guidance_actions=["create_successor", "record_no_followup"],
        todo_actions=[
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": "run a bounded vision-gap replan",
            }
        ],
        stop_condition="stop at private material or owner-only decisions",
        recommended_action="create a successor or record no-follow-up",
        extra_fields={"source": "goal_frontier_projection"},
    )

    assert payload["schema_version"] == AUTONOMOUS_REPLAN_SCHEMA_VERSION, payload
    assert payload["required"] is True, payload
    assert payload["agent_id"] == "codex-product-capability", payload
    assert payload["triggers"][0]["kind"] == "vision_acceptance_gap", payload
    assert payload["guidance_actions"] == ["create_successor", "record_no_followup"], payload
    assert payload["todo_actions"][0]["priority"] == "P1", payload
    assert payload["source"] == "goal_frontier_projection", payload

    unscoped_payload = build_autonomous_replan_obligation_payload(
        schema_version=AUTONOMOUS_REPLAN_SCHEMA_VERSION,
        agent_id=None,
        include_agent_id=True,
        stall_threshold=1,
        trigger_count=1,
        triggers=[],
        guidance_actions=[],
        todo_actions=[],
        stop_condition="stop at owner-only decisions",
        recommended_action="run a bounded replan",
    )
    assert "agent_id" in unscoped_payload, unscoped_payload
    assert unscoped_payload["agent_id"] is None, unscoped_payload


def direct_state_obligation() -> dict[str, object] | None:
    return direct_autonomous_replan_obligation_from_state(
        STATE_TEXT,
        agent_todos=AGENT_TODOS,
        section_headings=AUTONOMOUS_REPLAN_SECTION_HEADINGS,
        section_parser=active_state_sections,
        section_entries=active_state_section_entries,
        public_safe_compact_text=public_safe_compact_text,
        build_autonomous_replan_obligation=build_autonomous_replan_obligation,
    )


def main() -> int:
    assert_payload_builder_contract()

    regular = assert_parity(
        [
            {
                "kind": "run_history_no_progress_repeat",
                "section": "run_history",
                "text": "two stalled turns repeated",
            }
        ]
    )
    assert regular["schema_version"] == AUTONOMOUS_REPLAN_SCHEMA_VERSION, regular
    assert regular["stall_threshold"] == AUTONOMOUS_REPLAN_STALL_THRESHOLD, regular
    assert regular["todo_actions"][0]["action"] == "split", regular
    assert regular["todo_actions"][1]["action"] == "add", regular
    assert regular["agent_id"] == "codex-control-plane", regular

    conflicting_agents = assert_parity(
        [
            {"kind": "no_progress_streak", "agent_id": "codex-a"},
            {"kind": "repeated_action_loop", "agent_id": "codex-b"},
        ]
    )
    assert "agent_id" not in conflicting_agents, conflicting_agents

    dead_monitor = assert_parity(
        [
            {
                "kind": "dead_monitor_repeat",
                "monitor_target_id": "stable-monitor-target",
                "run_count": DEAD_MONITOR_REPEAT_THRESHOLD,
                "threshold": DEAD_MONITOR_REPEAT_THRESHOLD,
            }
        ]
    )
    assert dead_monitor["stall_threshold"] == DEAD_MONITOR_REPEAT_THRESHOLD, dead_monitor
    assert dead_monitor["dead_monitor_detector"]["monitor_target_id"] == "stable-monitor-target"
    assert dead_monitor["guidance_actions"][0] == "set_watch_expiry", dead_monitor

    periodic = assert_parity(
        [
            {
                "kind": "periodic_review_due",
                "section": "run_history",
                "text": "periodic review threshold reached",
            }
        ]
    )
    assert periodic["todo_actions"][-1]["action"] == "ask_decision", periodic
    assert "periodic review" in periodic["recommended_action"], periodic

    assert build_autonomous_replan_obligation([], agent_todos=AGENT_TODOS) is None

    state_wrapper = autonomous_replan_obligation(STATE_TEXT, agent_todos=AGENT_TODOS)
    state_direct = direct_state_obligation()
    assert state_wrapper == state_direct, (state_wrapper, state_direct)
    assert state_wrapper is not None, state_wrapper
    assert state_wrapper["trigger_count"] == 3, state_wrapper
    assert state_wrapper["agent_id"] == "codex-control-plane", state_wrapper
    assert [item["kind"] for item in state_wrapper["triggers"]] == [
        "no_progress_streak",
        "repeated_action_loop",
        "periodic_review",
    ], state_wrapper

    print("autonomous-replan-obligation-readmodel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
