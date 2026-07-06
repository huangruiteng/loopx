#!/usr/bin/env python3
"""Smoke-test SkillsBench post-run debug gate attribution edges."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import build_skillsbench_post_run_debug_gate  # noqa: E402


def test_countable_zero_keeps_solution_attribution() -> None:
    compact = {
        "benchmark_id": "skillsbench@1.1",
        "official_score": 0.0,
        "official_score_status": "completed",
        "official_task_score": {
            "kind": "skillsbench_verifier_reward",
            "passed": False,
            "value": 0.0,
        },
        "score_failure_attribution": "official_verifier_solution_failure",
        "failure_attribution_labels": ["official_verifier_solution_failure"],
        "case_event_timeline": {
            "schema_version": "skillsbench_case_event_timeline_v0",
            "source": "compact_public_signals",
            "raw_material_recorded": False,
            "events": [
                {
                    "phase": "controller",
                    "event": "controller_decision_loop",
                    "status": "stopped_after_one_round",
                },
                {
                    "phase": "scoring",
                    "event": "official_score_closeout",
                    "status": "completed",
                    "official_score_passed": False,
                },
                {
                    "phase": "closeout",
                    "event": "agent_bridge_closeout",
                    "status": "missing",
                },
            ],
        },
        "interaction_counters": {
            "remote_command_file_bridge_agent_task_facing_operation_count": 15,
            "remote_command_file_bridge_agent_task_facing_success_count": 15,
        },
    }

    gate = build_skillsbench_post_run_debug_gate(compact)

    assert gate["packet_complete"] is True, gate
    assert gate["case_closeout_complete"] is True, gate
    assert gate["normal_progress_allowed"] is True, gate
    assert gate["next_case_gate"] == "open_with_attribution", gate
    assert gate["attribution_layer"] == "solution_level_unknown", gate
    assert gate["first_blocker"] == "official_verifier_solution_failure", gate
    assert gate["missing_field_count"] == 0, gate


def main() -> None:
    test_countable_zero_keeps_solution_attribution()
    print("skillsbench-post-run-debug-gate-smoke: ok")


if __name__ == "__main__":
    main()
