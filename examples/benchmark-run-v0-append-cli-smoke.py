#!/usr/bin/env python3
"""Smoke-test appending compact benchmark events through the LoopX CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import (  # noqa: E402
    benchmark_comparison_decision_note,
    collect_status,
    compact_benchmark_comparison,
)


GOAL_ID = "benchmark-append-cli-fixture"
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
            "input_tokens": 1234,
            "cache_tokens": 100,
            "output_tokens": 321,
            "cost_usd": 0.45,
        },
        "trials": [
            {
                "task_id": "terminal-bench-hello",
                "trial_name": "terminal-bench-hello__codex__attempt-1",
                "source": BENCHMARK_ID,
                "reward": {"reward": 1.0},
                "metrics": {
                    "input_tokens": 1234,
                    "cache_tokens": 100,
                    "output_tokens": 321,
                    "cost_usd": 0.45,
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


def benchmark_comparison_event() -> dict[str, Any]:
    return {
        "schema_version": "benchmark_comparison_v0",
        "task_id": "mini_control_plane_repair_v0",
        "comparison_id": "mini_control_plane_repair_v0_ab",
        "benchmark_id": "local-deterministic",
        "mode_pair": ["without_loopx", "with_loopx"],
        "baseline_scenario_id": "without_loopx",
        "treatment_scenario_id": "with_loopx",
        "scenario_count": 2,
        "both_success": True,
        "official_task_score_delta": 0.0,
        "control_plane_score_delta": 0.143,
        "cost_delta_usd": 0.274,
        "with_loopx_overhead_ms": 12.5,
        "with_loopx_extra_writebacks": 3,
        "with_loopx_extra_spends": 3,
        "failure_attribution_labels": ["verifier_platform_probe_failure"],
        "baseline_failure_gate": {
            "schema_version": "benchmark_baseline_failure_gate_v0",
            "baseline_mode": "codex_cli_goal_mode",
            "baseline_scenario_id": "without_loopx",
            "baseline_terminal_state": "failed",
            "baseline_failed": True,
            "failure_phase": "validation",
            "failure_class": "verifier_platform_probe_failure",
            "failure_attribution_labels": ["verifier_platform_probe_failure"],
            "control_plane_addressable": True,
            "treatment_eligible": True,
            "same_task_semantics": True,
            "same_runner_protocol": True,
            "trace_publicness_verified": True,
            "baseline_attempt_count": 1,
            "minimum_next_evidence": "run the LoopX treatment arm on the same public task",
            "evidence_refs": ["benchmark_result_v0:without_loopx"],
            "raw_log_path": "/" + "tmp/private/raw.log",
        },
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "raw_trace_excluded": True,
            "credential_values_recorded": False,
            "private_path_recorded": True,
        },
        "decision": {
            "score_uplift": False,
            "validation_enhancement_point": True,
            "why": "Worker writeback and failure attribution improved while official score delta stayed zero.",
            "raw_log_path": "/" + "tmp/private/raw.log",
        },
        "result_refs": [
            {
                "scenario_id": "without_loopx",
                "task_id": "mini_control_plane_repair_v0",
                "result_id": "result_without_loopx",
                "raw_log_path": "/" + "tmp/private/raw.log",
            },
            {
                "scenario_id": "with_loopx",
                "task_id": "mini_control_plane_repair_v0",
                "result_id": "result_with_loopx",
            },
        ],
        "metrics_compared": [
            "official_task_score",
            "control_plane_score",
            "writeback_count",
            "spend_count",
        ],
        "interrupt_fixture_markers": [
            "worker_kill_after_partial_goal_tick_writeback",
            "stale_latest_run_trap",
        ],
        "stop_conditions": [
            "do_not_run_real_benchmark",
            "do_not_upload_leaderboard_trace",
        ],
        "raw_thread_path": "/" + "Users/example/private/session.jsonl",
    }


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    benchmark_run_path = root / "benchmark_run.json"
    benchmark_result_path = root / "benchmark_result.json"
    benchmark_comparison_path = root / "benchmark_comparison.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-07T00:00:00+00:00\n"
        "---\n\n"
        "# Benchmark Append CLI Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Append compact benchmark_run_v0, benchmark_result_v0, and benchmark_comparison_v0 events through the CLI.\n\n"
        "## Next Action\n\n"
        "- Inspect the appended benchmark status/result projections.\n",
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
    write_json(benchmark_run_path, benchmark_run_event())
    write_json(benchmark_result_path, benchmark_result_event())
    write_json(benchmark_comparison_path, benchmark_comparison_event())
    return registry_path, runtime, benchmark_run_path, benchmark_result_path, benchmark_comparison_path


def run_cli(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


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


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-run-v0-append-") as tmp:
        registry_path, runtime, benchmark_run_path, benchmark_result_path, benchmark_comparison_path = write_fixture(Path(tmp))
        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"

        base_args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-benchmark-run",
            "--goal-id",
            GOAL_ID,
            "--benchmark-run-json",
            str(benchmark_run_path),
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "primary_goal_outcome",
        ]

        dry_run = run_cli(base_args)
        assert dry_run["ok"], dry_run
        assert dry_run["dry_run"] is True, dry_run
        assert dry_run["appended"] is False, dry_run
        assert not index_path.exists(), index_path
        assert_no_private_surface(dry_run["benchmark_run"])

        appended = run_cli([*base_args, "--execute"])
        assert appended["ok"], appended
        assert appended["dry_run"] is False, appended
        assert appended["appended"] is True, appended
        assert index_path.exists(), index_path
        assert_no_private_surface(appended["benchmark_run"])

        result_args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-benchmark-result",
            "--goal-id",
            GOAL_ID,
            "--benchmark-result-json",
            str(benchmark_result_path),
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "primary_goal_outcome",
        ]

        result_dry_run = run_cli(result_args)
        assert result_dry_run["ok"], result_dry_run
        assert result_dry_run["dry_run"] is True, result_dry_run
        assert result_dry_run["appended"] is False, result_dry_run
        assert_no_private_surface(result_dry_run["benchmark_result"])
        assert "changed_files" not in result_dry_run["benchmark_result"], result_dry_run

        result_appended = run_cli([*result_args, "--execute"])
        assert result_appended["ok"], result_appended
        assert result_appended["dry_run"] is False, result_appended
        assert result_appended["appended"] is True, result_appended
        assert_no_private_surface(result_appended["benchmark_result"])
        assert "changed_files" not in result_appended["benchmark_result"], result_appended

        index_records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(index_records) == 2, index_records
        assert index_records[0]["classification"] == "benchmark_run_v0", index_records
        assert index_records[0]["benchmark_run"]["schema_version"] == "benchmark_run_v0", index_records
        assert index_records[1]["classification"] == "benchmark_result_v0", index_records
        assert index_records[1]["benchmark_result"]["schema_version"] == "benchmark_result_v0", index_records
        assert "changed_files" not in index_records[1]["benchmark_result"], index_records

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        latest_runs = status["run_history"]["goals"][0]["latest_runs"]
        result_run = next(run for run in latest_runs if run.get("classification") == "benchmark_result_v0")
        run_event = next(run for run in latest_runs if run.get("classification") == "benchmark_run_v0")
        result_summary = result_run["benchmark_result_summary"]
        assert result_summary["schema_version"] == "benchmark_result_v0", result_summary
        assert result_summary["official_task_score"]["value"] == 1.0, result_summary
        assert result_summary["control_plane_score"]["schema_version"] == "control_plane_score_core_v0", result_summary
        assert result_summary["control_plane_score"]["value"] == 0.875, result_summary
        assert tuple(result_summary["control_plane_score"]["component_order"]) == CONTROL_PLANE_SCORE_COMPONENTS, result_summary
        assert "changed_files" not in result_summary, result_summary
        assert_no_private_surface(result_summary)

        comparison_args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-benchmark-comparison",
            "--goal-id",
            GOAL_ID,
            "--benchmark-comparison-json",
            str(benchmark_comparison_path),
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "primary_goal_outcome",
        ]

        comparison_dry_run = run_cli(comparison_args)
        assert comparison_dry_run["ok"], comparison_dry_run
        assert comparison_dry_run["dry_run"] is True, comparison_dry_run
        assert comparison_dry_run["appended"] is False, comparison_dry_run
        assert_no_private_surface(comparison_dry_run["benchmark_comparison"])
        assert "raw_thread_path" not in comparison_dry_run["benchmark_comparison"], comparison_dry_run
        assert "raw_log_path" not in json.dumps(comparison_dry_run["benchmark_comparison"], sort_keys=True), comparison_dry_run

        comparison_appended = run_cli([*comparison_args, "--execute"])
        assert comparison_appended["ok"], comparison_appended
        assert comparison_appended["dry_run"] is False, comparison_appended
        assert comparison_appended["appended"] is True, comparison_appended
        assert_no_private_surface(comparison_appended["benchmark_comparison"])

        summary = run_event["benchmark_run_summary"]
        assert summary["benchmark_id"] == BENCHMARK_ID, summary
        assert summary["progress"]["n_completed_trials"] == 1, summary
        assert summary["metrics"]["cost_usd"] == 0.45, summary
        assert summary["validation"]["all_passed"] is True, summary
        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        latest_runs = status["run_history"]["goals"][0]["latest_runs"]
        comparison_run = next(run for run in latest_runs if run.get("classification") == "benchmark_comparison_v0")
        comparison_summary = comparison_run["benchmark_comparison_summary"]
        assert comparison_summary["schema_version"] == "benchmark_comparison_v0", comparison_summary
        assert comparison_summary["comparison_id"] == "mini_control_plane_repair_v0_ab", comparison_summary
        assert comparison_summary["mode_pair"] == ["without_loopx", "with_loopx"], comparison_summary
        assert comparison_summary["official_task_score_delta"] == 0.0, comparison_summary
        assert comparison_summary["control_plane_score_delta"] == 0.143, comparison_summary
        assert comparison_summary["cost_delta_usd"] == 0.274, comparison_summary
        assert comparison_summary["both_success"] is True, comparison_summary
        assert comparison_summary["failure_attribution_labels"] == ["verifier_platform_probe_failure"], comparison_summary
        assert comparison_summary["baseline_failure_gate"] == {
            "schema_version": "benchmark_baseline_failure_gate_v0",
            "baseline_mode": "codex_cli_goal_mode",
            "baseline_scenario_id": "without_loopx",
            "baseline_terminal_state": "failed",
            "failure_phase": "validation",
            "failure_class": "verifier_platform_probe_failure",
            "minimum_next_evidence": "run the LoopX treatment arm on the same public task",
            "baseline_failed": True,
            "control_plane_addressable": True,
            "treatment_eligible": True,
            "same_task_semantics": True,
            "same_runner_protocol": True,
            "trace_publicness_verified": True,
            "baseline_attempt_count": 1,
            "failure_attribution_labels": ["verifier_platform_probe_failure"],
            "evidence_refs": ["benchmark_result_v0:without_loopx"],
        }, comparison_summary
        assert comparison_summary["claim_boundary"] == {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "raw_trace_excluded": True,
            "credential_values_recorded": False,
        }, comparison_summary
        assert comparison_summary["decision"]["score_uplift"] is False, comparison_summary
        assert comparison_summary["decision"]["validation_enhancement_point"] is True, comparison_summary
        assert "raw_log_path" not in json.dumps(comparison_summary["decision"], sort_keys=True), comparison_summary
        assert "raw_thread_path" not in comparison_summary, comparison_summary
        assert "raw_log_path" not in json.dumps(comparison_summary, sort_keys=True), comparison_summary
        assert_no_private_surface(comparison_summary)
        decision_note = comparison_run["benchmark_comparison_decision_note"]
        assert decision_note["schema_version"] == "benchmark_comparison_decision_note_v0", decision_note
        assert decision_note["source_schema_version"] == "benchmark_comparison_v0", decision_note
        assert decision_note["decision"] == "continue", decision_note
        assert decision_note["evidence_layer"] == "control_plane_only", decision_note
        assert decision_note["official_task_score_delta"] == 0.0, decision_note
        assert decision_note["control_plane_score_delta"] == 0.143, decision_note
        assert decision_note["failure_attribution_labels"] == ["verifier_platform_probe_failure"], decision_note
        assert decision_note["baseline_failure_gate"] == {
            "schema_version": "benchmark_baseline_failure_gate_v0",
            "baseline_mode": "codex_cli_goal_mode",
            "failure_phase": "validation",
            "failure_class": "verifier_platform_probe_failure",
            "baseline_failed": True,
            "control_plane_addressable": True,
            "treatment_eligible": True,
        }, decision_note
        assert decision_note["validation_enhancement_point"] is True, decision_note
        assert decision_note["score_uplift"] is False, decision_note
        assert "control-plane delta improved while official score delta stayed zero" in decision_note["may_claim"], decision_note
        assert "official leaderboard uplift" in decision_note["must_not_claim"], decision_note
        assert decision_note["report_section_hint"] == ["claim_boundary", "next_decision"], decision_note
        assert_no_private_surface(decision_note)

        failure_comparison = compact_benchmark_comparison(
            {
                "schema_version": "benchmark_comparison_v0",
                "task_id": "torch-tensor-parallelism",
                "comparison_id": "torch_tensor_parallelism_failure_triage",
                "benchmark_id": "terminal-bench@2.0",
                "mode_pair": ["hardened_codex_baseline", "codex_loopx_active_user"],
                "both_success": False,
                "official_task_score_delta": 0.0,
                "failure_attribution_labels": ["verifier_platform_probe_failure"],
                "decision": {
                    "score_uplift": False,
                    "validation_enhancement_point": True,
                    "why": "Treatment preserved worker writeback and failure attribution without changing official score.",
                },
                "claim_boundary": {
                    "leaderboard_claim_allowed": False,
                    "official_score_uplift_claim_allowed": False,
                    "assisted_collaboration_claim_allowed": True,
                    "raw_trace_excluded": True,
                    "credential_values_recorded": False,
                },
            }
        )
        failure_note = benchmark_comparison_decision_note(failure_comparison)
        assert failure_note["evidence_layer"] == "validation_enhancement_no_score_uplift", failure_note
        assert failure_note["decision"] == "continue", failure_note
        assert failure_note["failure_attribution_labels"] == ["verifier_platform_probe_failure"], failure_note
        assert failure_note["validation_enhancement_point"] is True, failure_note
        assert failure_note["score_uplift"] is False, failure_note
        assert "official score uplift" in failure_note["must_not_claim"], failure_note
        assert_no_private_surface(failure_note)

        gate_only_comparison = compact_benchmark_comparison(
            {
                "schema_version": "benchmark_comparison_v0",
                "task_id": "terminal-bench-goal-mode-failure",
                "comparison_id": "terminal_bench_goal_mode_failure_gate",
                "benchmark_id": "terminal-bench@2.0",
                "baseline_scenario_id": "codex_goal_mode",
                "treatment_scenario_id": "codex_loopx",
                "baseline_failure_gate": {
                    "baseline_mode": "codex_cli_goal_mode",
                    "baseline_scenario_id": "codex_goal_mode",
                    "baseline_terminal_state": "failed",
                    "baseline_failed": True,
                    "failure_phase": "writeback",
                    "failure_class": "worker_trace_without_benchmark_run_writeback",
                    "failure_attribution_labels": ["worker_trace_without_benchmark_run_writeback"],
                    "control_plane_addressable": True,
                    "treatment_eligible": True,
                    "minimum_next_evidence": "run same-task LoopX treatment with compact writeback required",
                },
            }
        )
        gate_only_note = benchmark_comparison_decision_note(gate_only_comparison)
        assert gate_only_note["evidence_layer"] == "baseline_failure_gate", gate_only_note
        assert gate_only_note["decision"] == "continue", gate_only_note
        assert gate_only_note["minimum_next_evidence"] == (
            "run same-task LoopX treatment with compact writeback required"
        ), gate_only_note
        assert "baseline failure is control-plane-addressable and treatment-eligible" in gate_only_note["may_claim"], gate_only_note
        assert "treatment uplift before paired treatment evidence exists" in gate_only_note["must_not_claim"], gate_only_note
        assert gate_only_note["baseline_failure_gate"]["control_plane_addressable"] is True, gate_only_note
        assert gate_only_note["baseline_failure_gate"]["treatment_eligible"] is True, gate_only_note
        assert_no_private_surface(gate_only_note)

        negative_gate_comparison = compact_benchmark_comparison(
            {
                "schema_version": "benchmark_comparison_v0",
                "task_id": "terminal-bench-non-addressable-failure",
                "comparison_id": "terminal_bench_negative_gate",
                "benchmark_id": "terminal-bench@2.0",
                "baseline_failure_gate": {
                    "baseline_mode": "codex_cli_goal_mode",
                    "baseline_terminal_state": "failed",
                    "baseline_failed": True,
                    "failure_phase": "task_semantics",
                    "failure_class": "domain_solution_missing",
                    "control_plane_addressable": False,
                    "treatment_eligible": False,
                    "negative_selection_reason": "baseline failure is not addressable by control-plane changes",
                    "raw_trace": "/" + "Users/private/session.jsonl",
                },
            }
        )
        negative_gate_note = benchmark_comparison_decision_note(negative_gate_comparison)
        assert negative_gate_note["evidence_layer"] == "baseline_failure_gate_negative_selection", negative_gate_note
        assert negative_gate_note["decision"] == "defer", negative_gate_note
        assert negative_gate_note["minimum_next_evidence"] == (
            "baseline failure is not addressable by control-plane changes"
        ), negative_gate_note
        assert negative_gate_note["baseline_failure_gate"]["control_plane_addressable"] is False, negative_gate_note
        assert negative_gate_note["baseline_failure_gate"]["treatment_eligible"] is False, negative_gate_note
        assert "treatment execution on non-addressable or unverified baseline failures" in negative_gate_note["must_not_claim"], negative_gate_note
        assert_no_private_surface(negative_gate_note)

        index_records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(index_records) == 3, index_records
        assert index_records[2]["classification"] == "benchmark_comparison_v0", index_records
        assert "raw_thread_path" not in index_records[2]["benchmark_comparison"], index_records
        assert "raw_log_path" not in json.dumps(index_records[2]["benchmark_comparison"], sort_keys=True), index_records

        packet = build_review_packet(status, goal_id=GOAL_ID)
        handoff = packet["project_agent_handoff"]
        assert "comparison=mini_control_plane_repair_v0_ab" in handoff, handoff
        assert "official_delta=0.0" in handoff, handoff
        assert "control_delta=0.143" in handoff, handoff
        assert "decision=continue" in handoff, handoff
        assert "layer=control_plane_only" in handoff, handoff
        assert_no_private_surface({"handoff": handoff})
        assert status["event_ledger_summary"]["totals"]["benchmark_runs_24h"] == 1, status
        assert_no_private_surface(summary)

    print("benchmark-run-v0-append-cli-smoke ok")


if __name__ == "__main__":
    main()
