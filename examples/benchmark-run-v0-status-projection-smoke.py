#!/usr/bin/env python3
"""Smoke-test benchmark_run_v0 projection through status and review packets."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import collect_status, compact_benchmark_run, render_status_markdown  # noqa: E402
from loopx.worker_bridge import build_worker_bridge_outcome  # noqa: E402


GOAL_ID = "benchmark-projection-fixture"
BENCHMARK_ID = "terminal-bench@2.0"
CONTROL_PLANE_SCORE_COMPONENTS = (
    "restartability",
    "stale_state_avoidance",
    "evidence_discipline",
    "boundary_safety",
    "writeback_quality",
    "gate_compliance",
    "failure_attribution",
    "overhead",
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def benchmark_run_event() -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": BENCHMARK_ID,
        "job_name": "terminal_bench_probe_v0_codex_builtin",
        "mode": "passive_observer",
        "agent": {
            "name": "codex",
            "model": "openai/gpt-5.1-codex-mini",
            "kwargs_keys": ["reasoning_effort"],
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 1200,
            "cache_tokens": 100,
            "output_tokens": 300,
            "cost_usd": 0.42,
        },
        "trials": [
            {
                "task_id": "terminal-bench-hello",
                "trial_name": "terminal-bench-hello__codex__attempt-1",
                "source": BENCHMARK_ID,
                "reward": {"reward": 1.0},
                "metrics": {
                    "input_tokens": 1200,
                    "cache_tokens": 100,
                    "output_tokens": 300,
                    "cost_usd": 0.42,
                },
                "trajectory_present": True,
                "verifier_reward_present": True,
                "artifact_manifest_present": True,
                "trial_result_present": True,
            }
        ],
        "validation": {
            "job_lock_present": True,
            "job_result_present": True,
            "trial_results_present": True,
            "verifier_reward_present": True,
            "agent_trajectory_recorded": True,
            "retry_progress_consistent": True,
            "no_leaderboard_upload_requested": True,
            "paths_redacted": True,
        },
        "worker_bridge_outcome": build_worker_bridge_outcome(
            worker_loopx_cli_call_total=6,
            counter_trace_present=True,
            runner_return_completed=True,
            official_score_completed=True,
            official_score_value=1.0,
            wall_time_seconds=60,
            wall_time_limit_seconds=900,
        ),
        "evidence_files": [
            "job:lock.json",
            "job:result.json",
            "trial:result.json",
            "trial:agent/trajectory.json",
            "trial:verifier/reward.json",
        ],
        "resume_or_inspect_commands": [
            "harbor job resume --job-path <job-dir>",
            "harbor view <jobs-dir>",
        ],
        "stop_conditions": [
            "do_not_run_docker_or_model_api_by_default",
            "do_not_upload_or_submit_leaderboard",
        ],
    }


def benchmark_result_event() -> dict[str, Any]:
    components = {
        "restartability": 1.0,
        "stale_state_avoidance": 1.0,
        "evidence_discipline": 1.0,
        "boundary_safety": 1.0,
        "writeback_quality": 1.0,
        "gate_compliance": 1.0,
        "failure_attribution": 1.0,
        "overhead": 0.0,
    }
    return {
        "schema_version": "benchmark_result_v0",
        "task_id": "mini_control_plane_repair_v0",
        "scenario_id": "with_loopx",
        "worker_mode": "deterministic",
        "harness_identity": "loopx",
        "worker_surface": "deterministic_shim",
        "terminal_state": "success",
        "official_task_score": {"kind": "deterministic_validation", "passed": True, "value": 1.0},
        "control_plane_score": {
            "schema_version": "control_plane_score_core_v0",
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": 0.875,
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "step_count": 3,
        "wall_time_ms": 42.0,
        "validation_pass_count": 4,
        "validation_fail_count": 0,
        "changed_file_count": 3,
        "changed_files": ["src/control_plane.py", "state/ACTIVE_GOAL_STATE.md"],
        "forbidden_access_count": 0,
        "stale_state_error_count": 0,
        "open_todo_preserved": True,
        "archive_hygiene_passed": True,
        "queue_contract_passed": True,
        "trace_publicness": "public",
        "failure_attribution_labels": [],
        "goal_tick_phase_coverage": 1.0,
        "writeback_count": 3,
        "spend_count": 3,
        "spend_before_validation_count": 0,
        "state_reconstructable": True,
    }


def write_fixture(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    run_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-07T00:00:00+00:00\n"
        "---\n\n"
        "# Benchmark Projection Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Continue passive benchmark projection without running Docker or model APIs.\n\n"
        "## Next Action\n\n"
        "- Inspect the benchmark_run_v0 status projection and choose the next fixture-backed slice.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-07T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-projection",
                    "status": "active-read-only",
                    "repo": str(project),
                    "state_file": state_file,
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "authority_sources": [],
                }
            ],
        },
    )

    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    run_json = runs_dir / "benchmark-run-v0.json"
    run_md = runs_dir / "benchmark-run-v0.md"
    index_path = runs_dir / "index.jsonl"
    run_record = {
        "generated_at": run_time,
        "goal_id": GOAL_ID,
        "classification": "benchmark_run_v0",
        "recommended_action": "inspect benchmark_run_v0 summary and continue passive projection work",
        "health_check": "benchmark_run_v0 fixture public-safe",
        "delivery_batch_scale": "implementation",
        "delivery_outcome": "primary_goal_outcome",
        "benchmark_run": benchmark_run_event(),
        "benchmark_result": benchmark_result_event(),
    }
    write_json(run_json, run_record)
    run_md.write_text("# Benchmark Run V0 Fixture\n", encoding="utf-8")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_record = {
        **run_record,
        "json_path": str(run_json),
        "markdown_path": str(run_md),
    }
    index_path.write_text(json.dumps(index_record, sort_keys=True) + "\n", encoding="utf-8")
    return registry_path


def assert_no_private_surface(summary: dict[str, Any]) -> None:
    text = json.dumps(summary, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        "OPENAI_API_KEY",
        "auth.json",
        "sessions/",
        "lark" + "office",
        "fei" + "shu.cn",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def assert_interrupted_worker_bridge_outcome_projection() -> None:
    compact = compact_benchmark_run(
        {
            "schema_version": "benchmark_run_v0",
            "benchmark_id": BENCHMARK_ID,
            "mode": "codex_loopx_active_worker",
            "real_run": True,
            "submit_eligible": False,
            "worker_bridge_outcome": build_worker_bridge_outcome(
                worker_loopx_cli_call_total=4,
                counter_trace_present=True,
                interrupted=True,
                interrupt_reason="controller_interrupt_after_wall_time_limit",
                wall_time_seconds=720,
                wall_time_limit_seconds=900,
            ),
            "official_task_score": {
                "kind": "sample_private_no_upload_interrupted",
            },
        }
    )
    assert compact is not None
    outcome = compact["worker_bridge_outcome"]
    assert outcome["schema_version"] == "loopx_worker_bridge_outcome_v0", outcome
    assert outcome["worker_bridge_verified"] is True, outcome
    assert outcome["runner_return_status"] == "interrupted_after_worker_bridge_success", outcome
    assert outcome["official_score_status"] == "blocked_pending_runner_return", outcome
    assert outcome["worker_loopx_cli_call_total"] == 4, outcome
    assert outcome["counter_trace_present"] is True, outcome
    policy = outcome["wall_time_policy"]
    assert policy["interrupted"] is True, outcome
    assert policy["changes_official_benchmark_timeout"] is False, outcome
    assert policy["changes_official_task_resources"] is False, outcome
    assert policy["leaderboard_claim_allowed"] is False, outcome
    assert "official_reward_complete" in outcome["claim_boundary"]["forbidden_claims"], outcome
    assert_no_private_surface(compact)


def main() -> None:
    assert_interrupted_worker_bridge_outcome_projection()
    with tempfile.TemporaryDirectory(prefix="benchmark-run-v0-status-") as tmp:
        registry_path = write_fixture(Path(tmp))
        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=None,
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        goal = status["run_history"]["goals"][0]
        latest = goal["latest_runs"][0]
        summary = latest["benchmark_run_summary"]
        assert summary["schema_version"] == "benchmark_run_v0", summary
        assert summary["source_runner"] == "harbor", summary
        assert summary["benchmark_id"] == BENCHMARK_ID, summary
        assert summary["progress"]["n_completed_trials"] == 1, summary
        assert summary["metrics"]["cost_usd"] == 0.42, summary
        outcome = summary["worker_bridge_outcome"]
        assert outcome["worker_bridge_verified"] is True, outcome
        assert outcome["runner_return_status"] == "completed", outcome
        assert outcome["official_score_status"] == "completed", outcome
        assert outcome["official_score_value"] == 1.0, outcome
        health = latest["worker_bridge_ingest_health_note"]
        assert health["schema_version"] == "worker_bridge_ingest_health_note_v0", health
        assert health["health_state"] == "official_score_ingested", health
        assert health["evidence_layer"] == "official_sample_score", health
        assert health["worker_loopx_cli_call_total"] == 6, health
        assert "leaderboard uplift" in health["must_not_claim"], health
        assert summary["validation"]["all_passed"] is True, summary
        assert summary["trials"][0]["reward"]["reward"] == 1.0, summary
        assert_no_private_surface(summary)
        assert_no_private_surface(health)

        result_summary = latest["benchmark_result_summary"]
        assert result_summary["schema_version"] == "benchmark_result_v0", result_summary
        assert result_summary["task_id"] == "mini_control_plane_repair_v0", result_summary
        assert result_summary["scenario_id"] == "with_loopx", result_summary
        assert result_summary["official_task_score"]["value"] == 1.0, result_summary
        control_score = result_summary["control_plane_score"]
        assert control_score["schema_version"] == "control_plane_score_core_v0", result_summary
        assert control_score["aggregation"] == "unweighted_mean", result_summary
        assert control_score["value"] == 0.875, result_summary
        assert tuple(control_score["component_order"]) == CONTROL_PLANE_SCORE_COMPONENTS, result_summary
        assert "changed_files" not in result_summary, result_summary
        assert_no_private_surface(result_summary)

        event_ledger = status["event_ledger_summary"]
        assert event_ledger["totals"]["benchmark_runs_24h"] == 1, event_ledger
        assert event_ledger["totals"]["by_class_24h"]["evidence"] == 1, event_ledger
        latest_benchmark = event_ledger["goals"][0]["latest_benchmark_run"]
        assert latest_benchmark["benchmark_id"] == BENCHMARK_ID, latest_benchmark

        markdown = render_status_markdown(status)
        assert "benchmark_runs_24h=1" in markdown, markdown
        assert "benchmark_runs_7d=1" in markdown, markdown

        packet = build_review_packet(status, goal_id=GOAL_ID)
        assert packet["ok"], packet
        assert "benchmark=terminal-bench@2.0" in packet["project_agent_handoff"], packet["project_agent_handoff"]
        assert "completed=1/1" in packet["project_agent_handoff"], packet["project_agent_handoff"]
        assert "reward=1.0" in packet["project_agent_handoff"], packet["project_agent_handoff"]
        assert "worker_bridge_health=official_score_ingested" in packet["project_agent_handoff"], packet["project_agent_handoff"]
        assert "result=mini_control_plane_repair_v0" in packet["project_agent_handoff"], packet["project_agent_handoff"]
        assert "control=0.875" in packet["project_agent_handoff"], packet["project_agent_handoff"]
        assert_no_private_surface({"project_agent_handoff": packet["project_agent_handoff"]})

    print("benchmark-run-v0-status-projection-smoke ok")


if __name__ == "__main__":
    main()
