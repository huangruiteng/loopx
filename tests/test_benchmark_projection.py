from __future__ import annotations

from loopx.benchmark_adapters.skillsbench_signals import (
    build_skillsbench_solution_quality_signals,
)
from loopx.control_plane.runtime.benchmark_projection import (
    build_benchmark_solution_quality_signals,
)


def test_generic_solution_quality_projection_preserves_legacy_adapter_parity() -> None:
    benchmark_run = {
        "benchmark_id": "terminal-bench@2.0",
        "official_score": 0.5,
        "interaction_counters": {
            "remote_command_file_bridge_agent_task_facing_operation_count": 2,
        },
        "failure_attribution_labels": ["partial_trajectory"],
    }

    generic = build_benchmark_solution_quality_signals(benchmark_run)

    assert generic == build_skillsbench_solution_quality_signals(benchmark_run)
    assert generic["schema_version"] == "skillsbench_solution_quality_signals_v0"
    assert generic["outcome_class"] == "partial_nonpass"
    assert generic["worker_activity"]["task_facing_activity_observed"] is True
    assert generic["solution_action_labels"] == [
        "partial_nonpass_official_score",
        "partial_trajectory_public_label_present",
        "rubric_miss_labels_unavailable_compact_only",
    ]
