#!/usr/bin/env python3
"""Smoke-test Harbor reducer ingestion of prompt-driven GH lifecycle proof."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.terminal_bench import (  # noqa: E402
    build_terminal_bench_harbor_result_benchmark_run,
)
from loopx.status import compact_benchmark_run  # noqa: E402


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_prompt_driven_fixture(root: Path) -> Path:
    run_root = root / "terminal-bench-prompt-driven-run"
    job_dir = run_root / "jobs" / "swe-marathon-zstd-decoder-gh-treatment"
    trial_dir = job_dir / "zstd-decoder__prompt"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_access_packet_mode": "full",
            "loopx_cli_bridge_enabled": True,
            "loopx_goal_id": "benchmark-case-terminal-bench-zstd-decoder-test",
        },
    }
    write_json(
        job_dir / "lock.json",
        {
            "schema_version": 1,
            "invocation": [
                "harbor",
                "run",
                "--dataset",
                "terminal-bench-sample@2.0",
                "--include-task-name",
                "zstd-decoder",
            ],
            "trials": [
                {
                    "task": {
                        "name": "zstd-decoder",
                        "source": "terminal-bench-sample",
                    },
                    "agent": agent,
                }
            ],
        },
    )
    write_json(
        job_dir / "config.json",
        {
            "job_name": job_dir.name,
            "timeout_multiplier": 1.0,
            "agent_timeout_multiplier": None,
            "verifier_timeout_multiplier": None,
            "agent_setup_timeout_multiplier": None,
            "environment_build_timeout_multiplier": None,
        },
    )
    write_json(
        job_dir / "result.json",
        {
            "id": "job-id",
            "started_at": "2026-06-21T10:00:00Z",
            "updated_at": "2026-06-21T10:15:30Z",
            "finished_at": "2026-06-21T10:15:30Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 0,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
            },
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "zstd-decoder",
            "trial_name": "zstd-decoder__prompt",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {},
        },
    )
    prompt_counts = {
        "quota_should_run": 1,
        "todo_claim": 1,
        "status": 1,
        "todo_update": 1,
        "refresh_state": 1,
        "quota_spend": 1,
    }
    controller_trace = {
        "schema_version": "harbor_host_prompt_polling_controller_trace_v0",
        "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_agent_trajectory_recorded": False,
        "max_rounds_budget": 5,
        "max_round_observed": 1,
        "initial_prompt_count": 1,
        "followup_prompt_count": 0,
        "controller_action_decisions": 1,
        "completion_marker_observed_count": 0,
        "round_timeout_sec": 900.0,
        "last_decision": "harbor_prompt_polling_round_timeout_before_completion",
    }
    work_dir = trial_dir / "agent" / "host-codex-goal-fixture"
    write_json(
        work_dir / "loopx_prompt_driven_trace.public.json",
        {
            "schema_version": "loopx_prompt_driven_case_trace_v0",
            "command_count": sum(prompt_counts.values()),
            "event_kind_counts": prompt_counts,
            "lifecycle_observed": True,
            "raw_commands_recorded": False,
            "raw_output_recorded": False,
        },
    )
    write_json(
        work_dir / "loopx_controller_trace.public.json",
        controller_trace,
    )
    write_json(
        work_dir / "app_server_goal_turn.compact.json",
        {
            "schema_version": "codex_app_server_goal_turn_driver_v0",
            "first_blocker": "harbor_prompt_polling_round_timeout_before_completion",
            "turn_completed_observed": False,
            "loopx_controller_trace_present": True,
            "loopx_controller_trace": controller_trace,
            "loopx_prompt_driven_case_cli_call_count": sum(prompt_counts.values()),
            "loopx_prompt_driven_event_counts": prompt_counts,
            "loopx_prompt_driven_lifecycle_observed": True,
            "strict_loopx_treatment_claim_allowed": True,
            "loopx_treatment_claim_blocker": "none",
        },
    )
    return job_dir


def assert_prompt_driven_result(payload: dict) -> None:
    assert payload["worker_bridge_materialization_status"] == "verified", payload
    assert payload["worker_bridge_materialization_blocker"] == "none", payload
    assert payload["loopx_worker_cli_bridge_trace_observed"] is True, payload
    assert payload["loopx_prompt_driven_lifecycle_observed"] is True, payload
    assert payload["loopx_prompt_driven_case_cli_call_count"] == 6, payload
    assert payload["loopx_controller_trace_present"] is True, payload
    assert payload["loopx_controller_trace_public_safe"] is True, payload
    assert payload["controller_max_rounds_budget"] == 5, payload
    assert payload["controller_max_round_observed"] == 1, payload
    assert payload["controller_followup_prompt_count"] == 0, payload
    assert payload["controller_round_timeout_sec"] == 900.0, payload
    assert payload["controller_turn_completed_observed"] is False, payload
    assert (
        payload["controller_last_decision"]
        == "harbor_prompt_polling_round_timeout_before_completion"
    ), payload
    assert payload["worker_loopx_cli_call_total"] == 6, payload
    assert (
        payload["first_blocker"]
        == "harbor_prompt_polling_round_timeout_before_completion"
    ), payload
    assert payload["strict_loopx_treatment_claim_allowed"] is True, payload
    assert payload["loopx_treatment_claim_blocker"] == "none", payload
    validation = payload["validation"]
    assert validation["worker_counter_trace_loaded"] is True, validation
    assert validation["worker_benchmark_run_file_present"] is True, validation
    assert validation["worker_benchmark_run_schema_ok"] is True, validation
    assert validation["worker_bridge_materialized_when_required"] is True, validation
    assert validation["loopx_controller_trace_present"] is True, validation
    assert validation["loopx_controller_trace_public_safe"] is True, validation
    overhead = payload["overhead_attribution_counters"]
    assert (
        overhead["attribution_granularity"]
        == "prompt_driven_case_local_cli_counts"
    ), overhead
    assert overhead["loopx_cli_call_total"] == 6, overhead
    outcome = payload["worker_bridge_outcome"]
    assert outcome["worker_bridge_verified"] is True, outcome
    assert outcome["prompt_driven_loopx_lifecycle_observed"] is True, outcome


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-prompt-driven-reducer-") as tmp:
        job_dir = write_prompt_driven_fixture(Path(tmp))
        payload = build_terminal_bench_harbor_result_benchmark_run(job_dir)
        assert_prompt_driven_result(payload)
        compact = compact_benchmark_run(payload)
        assert compact is not None
        assert compact["worker_bridge_materialization_status"] == "verified", compact
        assert compact["loopx_prompt_driven_lifecycle_observed"] is True, compact
        assert compact["loopx_controller_trace_present"] is True, compact
        assert compact["controller_max_round_observed"] == 1, compact
        assert compact["controller_followup_prompt_count"] == 0, compact
        assert compact["controller_round_timeout_sec"] == 900.0, compact
        assert (
            compact["controller_last_decision"]
            == "harbor_prompt_polling_round_timeout_before_completion"
        ), compact
        output_path = Path(tmp) / "harbor_job_result.compact.json"
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "harbor_job_result_reducer.py"),
                "--job-dir",
                str(job_dir),
                "--benchmark-id",
                "terminal-bench",
                "--mode",
                "codex_loopx",
                "--output-json",
                str(output_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        reduced = json.loads(output_path.read_text(encoding="utf-8"))
        reduced_compact = reduced["compact_benchmark_run"]
        assert reduced["ok"] is True, reduced
        assert (
            reduced_compact["worker_bridge_materialization_status"] == "verified"
        ), reduced_compact
        assert (
            reduced_compact["first_blocker"]
            == "harbor_prompt_polling_round_timeout_before_completion"
        ), reduced_compact
        assert (
            reduced_compact["loopx_prompt_driven_case_cli_call_count"] == 6
        ), reduced_compact
        assert reduced_compact["loopx_controller_trace_present"] is True, (
            reduced_compact
        )
        assert reduced_compact["controller_max_round_observed"] == 1, reduced_compact
        assert reduced_compact["controller_followup_prompt_count"] == 0, (
            reduced_compact
        )
        assert reduced_compact["controller_round_timeout_sec"] == 900.0, (
            reduced_compact
        )
    print("terminal-bench harbor prompt-driven reducer smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
