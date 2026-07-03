#!/usr/bin/env python3
"""Smoke-test autonomous replan obligation builder read-model parity."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.projections.autonomous_replan_obligation import (  # noqa: E402
    build_autonomous_replan_obligation as direct_build_autonomous_replan_obligation,
)
from loopx.status import (  # noqa: E402
    AUTONOMOUS_REPLAN_SCHEMA_VERSION,
    AUTONOMOUS_REPLAN_STALL_THRESHOLD,
    DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
    DEAD_MONITOR_REPEAT_THRESHOLD,
    build_autonomous_replan_obligation,
    public_safe_compact_text,
)


AGENT_TODOS = {
    "first_open_items": [
        {
            "priority": "P2",
            "text": "[P2] Continue canary-gated control-plane read-model cleanup.",
        }
    ]
}


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


def main() -> int:
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
    print("autonomous-replan-obligation-readmodel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
