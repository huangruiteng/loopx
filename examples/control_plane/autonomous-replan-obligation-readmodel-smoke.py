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
from loopx.control_plane.work_items.project_asset import (  # noqa: E402
    attach_active_state_project_asset_fields,
)
from loopx.control_plane.goals.goal_frontier import (  # noqa: E402
    select_autonomous_replan_obligation,
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
    autonomous_replan_obligation_from_runs,
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


def assert_peer_latest_run_does_not_hide_agent_stall() -> None:
    agent_id = "codex-quality-qualification"
    peer_id = "codex-main-control"
    target = {
        "schema_version": "quota_monitor_target_v0",
        "target_id": "blocked-successor",
        "monitor_mode": "blocked_successor_wait_without_material_transition",
        "effective_action": "monitor_quiet_skip",
        "agent_id": agent_id,
        "frontier_identity": "stable-frontier",
    }
    latest_runs = [
        {
            "classification": "peer_delivery",
            "generated_at": "2026-07-21T00:03:00+00:00",
            "agent_id": peer_id,
            "delivery_outcome": "outcome_progress",
        },
        {
            "classification": "quota_monitor_poll",
            "generated_at": "2026-07-21T00:02:00+00:00",
            "agent_id": agent_id,
            "health_check": "blocked successor wait unchanged; bounded replan after two polls",
            "monitor_target": target,
        },
        {
            "classification": "quota_monitor_poll",
            "generated_at": "2026-07-21T00:01:00+00:00",
            "agent_id": agent_id,
            "health_check": "blocked successor wait unchanged; bounded replan after two polls",
            "monitor_target": target,
        },
    ]

    obligation = autonomous_replan_obligation_from_runs(
        latest_runs,
        agent_todos=None,
        agent_id=agent_id,
    )
    assert obligation is not None, obligation
    assert obligation["agent_id"] == agent_id, obligation
    assert obligation["frontier_identity"] == "stable-frontier", obligation

    item = {
        "agent_todos": AGENT_TODOS,
        "project_asset": {},
    }
    attach_active_state_project_asset_fields(
        item,
        latest_runs=latest_runs,
        autonomous_replan_obligation_from_runs=autonomous_replan_obligation_from_runs,
    )
    selected = select_autonomous_replan_obligation(
        item,
        item["project_asset"],
        agent_id=agent_id,
    )
    assert selected == obligation, (selected, obligation)
    assert select_autonomous_replan_obligation(
        item,
        item["project_asset"],
        agent_id=peer_id,
    ) is None


def main() -> int:
    assert_payload_builder_contract()
    assert_peer_latest_run_does_not_hide_agent_stall()

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
    assert "agent_todo_writeback_required" not in regular, regular

    empty_frontier = direct_build_autonomous_replan_obligation(
        [
            {
                "kind": "run_history_no_progress_repeat",
                "section": "run_history",
                "text": "two stalled turns left no runnable agent todo",
            }
        ],
        agent_todos=None,
        public_safe_compact_text=public_safe_compact_text,
        autonomous_replan_schema_version=AUTONOMOUS_REPLAN_SCHEMA_VERSION,
        autonomous_replan_stall_threshold=AUTONOMOUS_REPLAN_STALL_THRESHOLD,
        dead_monitor_repeat_threshold=DEAD_MONITOR_REPEAT_THRESHOLD,
        dead_monitor_repeat_schema_version=DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
    )
    assert empty_frontier is not None, empty_frontier
    assert empty_frontier["agent_todo_writeback_required"] is True, empty_frontier
    assert empty_frontier["todo_actions"][0] == {
        "action": "add",
        "role": "agent",
        "priority": "P1",
        "text": (
            "write a compact replan record naming trigger, selected next slice, "
            "validation command, and stop condition"
        ),
    }, empty_frontier

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
