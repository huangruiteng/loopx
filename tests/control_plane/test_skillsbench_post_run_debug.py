from __future__ import annotations

from loopx import status
from loopx.control_plane.runtime.skillsbench_post_run_debug import (
    build_skillsbench_post_run_debug_gate,
)


def test_status_preserves_skillsbench_post_run_debug_import() -> None:
    assert (
        status.build_skillsbench_post_run_debug_gate
        is build_skillsbench_post_run_debug_gate
    )


def test_non_skillsbench_rows_do_not_project_a_debug_gate() -> None:
    assert build_skillsbench_post_run_debug_gate({"benchmark_id": "other"}) == {}
    assert build_skillsbench_post_run_debug_gate({}) == {}


def test_missing_timeline_blocks_progress_with_public_boundary() -> None:
    gate = build_skillsbench_post_run_debug_gate(
        {
            "benchmark_id": "skillsbench@1.1",
            "official_task_score": {"passed": False, "value": 0.0},
        }
    )

    assert gate["packet_complete"] is False
    assert gate["case_closeout_complete"] is False
    assert gate["next_case_gate"] == "blocked_missing_debug_packet"
    assert gate["first_blocker"] == "case_event_timeline"
    assert gate["raw_material_recorded"] is False
    assert gate["boundary"] == {
        "task_text_read": False,
        "logs_read": False,
        "trajectory_read": False,
        "verifier_output_tail_public": False,
    }


def test_countable_zero_keeps_solution_level_attribution() -> None:
    gate = build_skillsbench_post_run_debug_gate(
        {
            "benchmark_id": "skillsbench@1.1",
            "official_score_status": "completed",
            "official_task_score": {"passed": False, "value": 0.0},
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
            },
        }
    )

    assert gate["packet_complete"] is True
    assert gate["case_closeout_complete"] is True
    assert gate["normal_progress_allowed"] is True
    assert gate["next_case_gate"] == "open_with_attribution"
    assert gate["attribution_layer"] == "solution_level_unknown"
    assert gate["first_blocker"] == "official_verifier_solution_failure"
