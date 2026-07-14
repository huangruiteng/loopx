#!/usr/bin/env python3
"""Smoke-test read-only handling of retired Harbor prompt-polling traces."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.terminal_bench import (  # noqa: E402
    _terminal_bench_prompt_driven_loopx_observation,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-historical-polling-read-") as tmp:
        job_dir = Path(tmp) / "jobs" / "historical-job"
        work_dir = job_dir / "trial" / "agent" / "host-worker"
        write_json(
            work_dir / "loopx_prompt_driven_trace.public.json",
            {
                "schema_version": "loopx_prompt_driven_case_trace_v0",
                "command_count": 2,
                "event_kind_counts": {"quota_should_run": 1, "todo_update": 1},
                "lifecycle_observed": True,
            },
        )
        write_json(
            work_dir / "loopx_controller_trace.public.json",
            {
                "schema_version": "harbor_host_prompt_polling_controller_trace_v0",
                "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                "raw_task_text_recorded": False,
                "raw_verifier_output_recorded": False,
                "raw_agent_trajectory_recorded": False,
                "initial_prompt_count": 1,
                "followup_prompt_count": 1,
            },
        )
        write_json(
            work_dir / "app_server_goal_turn.compact.json",
            {
                "schema_version": "codex_app_server_goal_turn_driver_v0",
                "strict_loopx_treatment_claim_allowed": True,
                "loopx_treatment_claim_blocker": "none",
            },
        )

        observed = _terminal_bench_prompt_driven_loopx_observation(job_dir)
        assert observed["historical_route_read_only"] is True, observed
        assert observed["strict_loopx_treatment_claim_allowed"] is False, observed
        assert observed["loopx_treatment_claim_blocker"] == (
            "historical_nonproduct_invalid_for_comparison"
        ), observed
        assert observed["lifecycle_observed"] is True, observed

        packet_job_dir = Path(tmp) / "jobs" / "packet-only-job"
        packet_work_dir = packet_job_dir / "trial" / "agent" / "host-worker"
        write_json(
            packet_work_dir / "loopx_prompt_driven_trace.public.json",
            {
                "schema_version": "loopx_prompt_driven_case_trace_v0",
                "command_count": 2,
                "event_kind_counts": {"quota_should_run": 1, "todo_update": 1},
                "lifecycle_observed": True,
            },
        )
        write_json(
            packet_work_dir / "app_server_goal_turn.compact.json",
            {
                "schema_version": "codex_app_server_goal_turn_driver_v0",
                "strict_loopx_treatment_claim_allowed": False,
                "loopx_treatment_claim_blocker": "packet_only_no_max5_controller",
            },
        )
        packet_observed = _terminal_bench_prompt_driven_loopx_observation(
            packet_job_dir
        )
        assert packet_observed["historical_route_read_only"] is False, packet_observed
        assert packet_observed["strict_loopx_treatment_claim_allowed"] is False, (
            packet_observed
        )
        assert packet_observed["loopx_treatment_claim_blocker"] == (
            "packet_only_no_max5_controller"
        ), packet_observed

    print("terminal-bench historical prompt-polling read smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
