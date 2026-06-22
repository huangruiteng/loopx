#!/usr/bin/env python3
"""Smoke-test benchmark run ledger upsert and CLI writeback."""

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

from loopx.benchmark import build_terminal_bench_harbor_result_benchmark_run  # noqa: E402
from loopx.benchmark_ledger import (  # noqa: E402
    BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
    build_benchmark_run_ledger_entry,
    load_benchmark_run_ledger,
    render_benchmark_run_ledger_markdown,
    update_benchmark_run_ledger,
)
from loopx.status import compact_benchmark_run  # noqa: E402


GOAL_ID = "benchmark-run-ledger-fixture"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_registry(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-14T00:00:00+00:00\n"
        "---\n\n"
        "# Benchmark Run Ledger Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Ingest a compact run and update the benchmark ledger.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-14T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-ledger",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                }
            ],
        },
    )
    return registry_path, runtime


def write_goal_mode_model_access_failure_job(root: Path) -> Path:
    job_dir = root / "jobs" / "terminal_bench_2_0_ledger_fixture_codex_goal_mode_baseline"
    trial_dir = job_dir / "ledger-fixture__model"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.1-codex-max",
        "kwargs": {
            "loopx_mode": "codex_goal_mode_baseline",
            "loopx_ablation_mode": "codex_goal_mode_baseline",
            "loopx_access_packet_mode": "none",
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
                "terminal-bench@2.0",
                "--include-task-name",
                "ledger-fixture",
                "--agent-kwarg",
                "loopx_mode=codex_goal_mode_baseline",
                "--agent-kwarg",
                "loopx_access_packet_mode=none",
            ],
            "trials": [
                {
                    "task": {
                        "name": "ledger-fixture",
                        "source": "terminal-bench@2.0",
                        "path": "ledger-fixture",
                    },
                    "agent": agent,
                }
            ],
        },
    )
    write_json(job_dir / "config.json", {"job_name": job_dir.name})
    write_json(
        job_dir / "result.json",
        {
            "started_at": "2026-06-14T09:00:00Z",
            "updated_at": "2026-06-14T09:01:00Z",
            "finished_at": "2026-06-14T09:01:00Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
                "evals": {
                    "loopx-managed-codex__gpt-5.1-codex-max__terminal-bench": {
                        "n_trials": 1,
                        "n_errors": 1,
                        "metrics": [{"mean": 0.0}],
                    }
                },
            },
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "ledger-fixture",
            "trial_name": "ledger-fixture__model",
            "source": "terminal-bench@2.0",
            "config": {"agent": agent},
            "agent_result": {
                "n_input_tokens": None,
                "n_cache_tokens": None,
                "n_output_tokens": None,
                "cost_usd": None,
            },
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {
                "exception_type": "NonZeroAgentExitCodeError",
                "exception_message": "Command failed (exit 1): codex exec --model gpt-5.1-codex-max",
                "exception_traceback": (
                    "turn.failed invalid_request_error: the model is not supported "
                    "when using Codex with a ChatGPT account"
                ),
            },
        },
    )
    return job_dir


def test_ledger_entry_upsert_from_compact_run() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-module-") as tmp:
        root = Path(tmp)
        job_dir = write_goal_mode_model_access_failure_job(root)
        compact = compact_benchmark_run(build_terminal_bench_harbor_result_benchmark_run(job_dir))
        assert compact is not None, compact
        assert compact["score_failure_attribution"] == (
            "codex_model_access_unsupported_score_failure"
        ), compact
        entry = build_benchmark_run_ledger_entry(
            compact,
            artifact_ref=job_dir,
            result_ref=job_dir / "result.json",
            run_group_id="ledger-smoke",
            cwd=root,
        )
        assert entry["case_id"] == "ledger-fixture", entry
        assert entry["arm_id"] == "codex_goal_mode_baseline", entry
        assert entry["official_score"] == 0.0, entry
        assert entry["failure_class"] == "codex_model_access_unsupported_for_account", entry
        assert entry["failure_scope"] == "runner_or_setup", entry
        assert entry["repair_priority"] == "P0", entry
        assert entry["repair_class"] == "runner_model_access", entry
        assert entry["repair_profile"]["blocked_model_route"] == "gpt-5.1-codex-max", entry
        assert entry["repair_profile"]["recommended_model_route"] == "gpt-5.5", entry
        assert entry["repair_profile"]["required_preflight"] == [
            "codex_cli_minimal_model_probe"
        ], entry

        ledger_path = root / "ledger.json"
        first = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            artifact_ref=job_dir,
            result_ref=job_dir / "result.json",
            run_group_id="ledger-smoke",
            cwd=root,
        )
        second = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            artifact_ref=job_dir,
            result_ref=job_dir / "result.json",
            run_group_id="ledger-smoke",
            cwd=root,
        )
        assert first["entry"]["run_id"] == second["entry"]["run_id"], second
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["terminal-bench@2.0"]["cases"]["ledger-fixture"]
        assert len(case["runs"]) == 1, case
        assert case["latest_decision"]["decision"] == "baseline_model_access_repair_required", case
        assert case["latest_decision"]["repair_class"] == "runner_model_access", case
        rendered = render_benchmark_run_ledger_markdown(ledger)
        assert "## Repair Backlog" in rendered, rendered
        assert "runner_model_access" in rendered, rendered
        assert "blocked_model=gpt-5.1-codex-max" in rendered, rendered
        assert "rerun_model=gpt-5.5" in rendered, rendered
        assert (root / "ledger.md").exists(), "markdown view should be rendered"


def test_ledger_classifies_compact_trial_exception_failure() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_runtime_error_fixture_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "score_failure_attribution": "none",
        "trials": [
            {
                "task_id": "runtime-error-fixture",
                "exception_type": "RuntimeError",
            }
        ],
    }
    entry = build_benchmark_run_ledger_entry(compact)
    assert entry["case_id"] == "runtime-error-fixture", entry
    assert entry["official_score"] == 0.0, entry
    assert entry["failure_class"] == "agent_exception_before_solution_completion", entry
    assert entry["failure_scope"] == "case_or_solution", entry


def test_ledger_classifies_setup_timeout_before_generic_timeout() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_setup_timeout_fixture_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "score_failure_attribution": "none",
        "trials": [
            {
                "task_id": "setup-timeout-fixture",
                "exception_type": "AgentSetupTimeoutError",
            }
        ],
    }
    entry = build_benchmark_run_ledger_entry(compact)
    assert entry["case_id"] == "setup-timeout-fixture", entry
    assert entry["official_score"] == 0.0, entry
    assert entry["failure_class"] == "agent_setup_timeout_before_worker_start", entry
    assert entry["failure_scope"] == "runner_or_setup", entry
    assert entry["repair_priority"] == "P0", entry
    assert entry["repair_class"] == "runner_setup_timeout", entry
    profile = entry["repair_profile"]
    assert profile["required_launch_overrides"]["codex_install_strategy"] == (
        "require_existing_codex"
    ), profile
    assert profile["disallowed_launch_overrides"]["codex_install_strategy"] == (
        "runtime_install_if_missing"
    ), profile
    assert profile["required_launch_overrides"]["agent_setup_timeout_multiplier"] == 8, profile
    assert profile["required_launch_overrides"]["agent_timeout_multiplier"] == 8, profile
    assert "codex_cli_existing_in_worker_or_fail_fast_blocker" in profile[
        "required_preflight"
    ], profile


def test_ledger_routes_environment_setup_before_worker_separately() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_env_setup_fixture_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "score_failure_attribution": "agent_setup_score_failure",
        "failure_attribution_labels": [
            "environment_setup_failed_before_worker",
            "agent_setup_score_failure",
        ],
        "environment_setup_failure_before_worker_count": 1,
        "trials": [
            {
                "task_id": "env-setup-fixture",
                "worker_start_status": "environment_setup_failed_before_worker",
            }
        ],
    }
    entry = build_benchmark_run_ledger_entry(compact)
    assert entry["case_id"] == "env-setup-fixture", entry
    assert entry["failure_class"] == "environment_setup_failed_before_worker", entry
    assert entry["failure_scope"] == "runner_or_setup", entry
    assert entry["repair_priority"] == "P0", entry
    assert entry["repair_class"] == "benchmark_environment_setup_contract", entry
    profile = entry["repair_profile"]
    assert "environment_setup_readiness_preflight_before_repeat" in profile[
        "required_preflight"
    ], profile
    assert "codex_cli_existing_in_worker_or_fail_fast_blocker" not in profile[
        "required_preflight"
    ], profile


def test_ledger_promotes_setup_diagnostic_blocker_over_generic_setup_failure() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_setup_diagnostic_fixture_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "score_failure_attribution": "agent_setup_score_failure",
        "failure_attribution_labels": [
            "agent_process_nonzero_exit_before_solution_attempt",
            "agent_setup_failed_before_worker_start",
            "codex_cli_not_on_path",
            "pre_worker_startup_blocker_recorded",
        ],
        "worker_setup_diagnostic_blockers": ["codex_cli_not_on_path"],
        "worker_setup_diagnostic_file_count": 1,
        "worker_setup_diagnostic_schema_ok_count": 1,
        "trials": [
            {
                "task_id": "setup-diagnostic-fixture",
                "exception_type": "NonZeroAgentExitCodeError",
            }
        ],
    }
    entry = build_benchmark_run_ledger_entry(compact)
    assert entry["case_id"] == "setup-diagnostic-fixture", entry
    assert entry["failure_class"] == "codex_cli_not_on_path", entry
    assert entry["failure_scope"] == "runner_or_setup", entry
    assert entry["repair_priority"] == "P0", entry
    assert entry["repair_class"] == "runner_codex_cli_materialization", entry
    assert entry["setup_blockers"] == ["codex_cli_not_on_path"], entry
    assert "worker_setup_diagnostic.schema_ok" in entry["repair_profile"][
        "required_preflight"
    ], entry

    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-setup-diagnostic-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="setup-diagnostic-ledger-smoke",
            cwd=root,
        )
        rendered = (root / "ledger.md").read_text()
        assert "codex_cli_not_on_path" in rendered, rendered
        assert "runner_codex_cli_materialization" in rendered, rendered


def test_ledger_falls_back_to_terminal_bench_case_from_job_name() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_path_tracing_codex_goal_mode_baseline_real_no_upload_20260614T201017CST",
        "mode": "codex_goal_mode_baseline",
        "official_score_status": "missing",
    }
    entry = build_benchmark_run_ledger_entry(compact, arm_id="baseline")
    assert entry["case_id"] == "path-tracing", entry
    assert entry["case_ids"] == ["path-tracing"], entry
    assert entry["arm_id"] == "codex_goal_mode_baseline", entry
    assert entry["failure_class"] == "score_missing", entry
    assert entry["repair_class"] == "runner_result_materialization", entry


def test_ledger_scopes_worker_materialization_probe_as_startup_surface() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench-worker-materialization@v0",
        "job_name": "terminal_bench_nginx_request_logging_hardened_worker_materialization_runtime_probe_20260616T113050CST",
        "mode": "hardened_codex_baseline_worker_materialization_probe",
        "source_runner": "terminal_bench_worker_materialization_probe",
        "official_score_status": "not_run_worker_materialization_probe",
        "score_failure_attribution": "not_applicable_worker_materialization_probe",
        "worker_bridge_materialization_status": "worker_codex_materialization_verified",
        "worker_bridge_materialization_blocker": "none",
        "real_run": False,
        "startup_surface_calibration": True,
    }
    entry = build_benchmark_run_ledger_entry(
        compact,
        arm_id="hardened_codex_worker_materialization_runtime_probe",
    )
    assert entry["case_id"] == "nginx-request-logging", entry
    assert entry["failure_class"] == "not_applicable_worker_materialization_probe", entry
    assert entry["failure_scope"] == "startup_surface", entry
    assert entry["worker_bridge_status"] == "worker_codex_materialization_verified", (
        entry
    )


def test_ledger_skips_running_result_placeholder() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_train_fasttext_loopx_managed_codex_20260618T035534CST",
        "mode": "loopx_managed_codex",
        "official_score_status": "missing",
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 1,
            "n_pending_trials": 0,
        },
    }
    entry = build_benchmark_run_ledger_entry(
        compact,
        result_ref=Path("running-result.json"),
        run_group_id="terminal-bench-train-fasttext-managed-20260618T035534CST",
        cwd=REPO_ROOT,
    )
    assert entry["status"] == "running", entry
    assert entry["score_status"] == "missing", entry
    assert entry["failure_class"] == "score_missing", entry

    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-running-skip-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            result_ref=root / "result.json",
            run_group_id="terminal-bench-train-fasttext-managed-20260618T035534CST",
            cwd=root,
        )
        assert update["ok"] is True, update
        assert update["updated"] is False, update
        assert update["skipped"] is True, update
        assert update["skip_reason"] == (
            "benchmark_run_not_terminal_for_public_ledger"
        ), update
        assert not ledger_path.exists(), "running placeholders must not create public ledger"
        assert not (root / "ledger.md").exists(), "running placeholders must not render markdown"


def test_ledger_repair_backlog_uses_latest_run_per_arm() -> None:
    old_job_name = (
        "terminal_bench_2_0_path_tracing_codex_goal_mode_baseline_real_no_upload_20260614T200518CST"
    )
    new_job_name = (
        "terminal_bench_2_0_path_tracing_codex_goal_mode_baseline_real_no_upload_20260614T201017CST"
    )
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-supersede-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        write_json(
            ledger_path,
            {
                "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
                "updated_at": "2026-06-14T20:00:00+08:00",
                "benchmarks": {
                    "terminal-bench@2.0": {
                        "benchmark_id": "terminal-bench@2.0",
                        "cases": {
                            old_job_name: {
                                "case_id": old_job_name,
                                "latest_decision": {
                                    "decision": "baseline_result_materialization_repair_required"
                                },
                                "runs": [
                                    {
                                        "run_id": "oldmissing",
                                        "recorded_at": "2026-06-14T20:06:38+08:00",
                                        "benchmark_id": "terminal-bench@2.0",
                                        "case_id": old_job_name,
                                        "case_ids": [old_job_name],
                                        "arm_id": "baseline",
                                        "mode": "codex_goal_mode_baseline",
                                        "job_name": old_job_name,
                                        "score_status": "missing",
                                        "failure_class": "score_missing",
                                        "failure_scope": "score_missing",
                                        "repair_priority": "P0",
                                        "repair_class": "runner_result_materialization",
                                        "next_action": (
                                            "repair or ignore the incomplete runner materialization before treating this as case evidence"
                                        ),
                                    }
                                ],
                            }
                        },
                    }
                },
            },
        )
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run={
                "schema_version": "benchmark_run_v0",
                "benchmark_id": "terminal-bench@2.0",
                "job_name": new_job_name,
                "mode": "codex_goal_mode_baseline",
                "official_task_score": {
                    "kind": "harbor_verifier_reward",
                    "value": 1.0,
                    "passed": True,
                },
            },
            arm_id="baseline",
            run_group_id="path-tracing-rerun",
            recorded_at="2026-06-14T20:46:04+08:00",
            cwd=root,
        )
        ledger = load_benchmark_run_ledger(ledger_path)
        cases = ledger["benchmarks"]["terminal-bench@2.0"]["cases"]
        assert sorted(cases) == ["path-tracing"], cases
        case = cases["path-tracing"]
        assert len(case["runs"]) == 2, case
        assert case["latest_decision"]["decision"] == (
            "baseline_passed_not_current_treatment_priority"
        ), case
        rendered = render_benchmark_run_ledger_markdown(ledger)
        assert "runner_result_materialization" not in rendered, rendered
        assert old_job_name not in rendered.split("## Repair Backlog")[0], rendered


def test_ledger_requires_attribution_for_zero_score_without_failure_signal() -> None:
    compact = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_unattributed_fixture_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "score_failure_attribution": "none",
        "trials": [
            {
                "task_id": "unattributed-fixture",
                "exception_type": "none",
            }
        ],
    }
    entry = build_benchmark_run_ledger_entry(compact)
    assert entry["case_id"] == "unattributed-fixture", entry
    assert entry["official_score"] == 0.0, entry
    assert entry["failure_class"] == "score_failure_unattributed", entry
    assert entry["failure_scope"] == "attribution_required", entry
    assert entry["repair_class"] == "verifier_attribution_required", entry
    assert entry["next_action"] == (
        "collect finer compact failure attribution before launching treatment"
    ), entry

    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-unattributed-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="unattributed-ledger-smoke",
            cwd=root,
        )
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["terminal-bench@2.0"]["cases"][
            "unattributed-fixture"
        ]
        assert case["latest_decision"]["decision"] == (
            "baseline_failed_requires_attribution"
        ), case
        assert case["latest_decision"]["next_action"] == (
            "collect finer compact failure attribution before launching treatment"
        ), case


def test_paired_runner_setup_blocker_overrides_zero_delta_no_uplift() -> None:
    baseline = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_setup_timeout_fixture_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "score_failure_attribution": "none",
        "trials": [
            {
                "task_id": "paired-setup-timeout-fixture",
                "exception_type": "AgentSetupTimeoutError",
            }
        ],
    }
    treatment = {
        **baseline,
        "job_name": "terminal_bench_2_0_setup_timeout_fixture_codex_loopx",
        "mode": "codex_loopx",
        "loopx_inside_case": True,
    }
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-paired-setup-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=baseline,
            run_group_id="paired-setup-ledger-smoke",
            cwd=root,
        )
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=treatment,
            run_group_id="paired-setup-ledger-smoke",
            cwd=root,
        )
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["terminal-bench@2.0"]["cases"][
            "paired-setup-timeout-fixture"
        ]
        assert case["latest_decision"]["official_score_delta"] == 0.0, case
        assert case["latest_decision"]["decision"] == (
            "paired_baseline_setup_timeout_repair_required"
        ), case
        assert case["latest_decision"]["repair_class"] == "runner_setup_timeout", case


def test_verified_bridge_official_zero_routes_to_no_uplift_not_alignment() -> None:
    baseline = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_headless_terminal_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "score_failure_attribution": "official_verifier_solution_failure",
        "failure_attribution_labels": ["official_verifier_solution_failure"],
        "trials": [
            {
                "task_id": "headless-terminal",
                "exception_type": "none",
            }
        ],
    }
    treatment = {
        **baseline,
        "job_name": "terminal_bench_2_0_headless_terminal_codex_loopx_treatment",
        "mode": "codex_loopx",
        "loopx_inside_case": True,
        "worker_bridge_materialization_status": "verified",
        "score_failure_attribution": "worker_bridge_connected_official_score_failure",
        "failure_attribution_labels": [
            "official_verifier_solution_failure",
            "worker_bridge_connected_official_score_failure",
        ],
        "worker_self_validation_official_score_mismatch_count": 0,
        "worker_validation_scope_ambiguous_official_score_failure_count": 0,
        "worker_submit_eligible_mismatch_count": 0,
        "worker_bridge_writeback_loss_count": 0,
        "worker_startup_blocker_count": 0,
        "environment_setup_failure_before_worker_count": 0,
        "pre_worker_agent_setup_failure_count": 0,
    }
    treatment_entry = build_benchmark_run_ledger_entry(treatment, arm_id="treatment")
    assert treatment_entry["failure_class"] == "official_verifier_solution_failure", treatment_entry
    assert treatment_entry["failure_scope"] == "case_or_solution", treatment_entry
    assert "repair_class" not in treatment_entry, treatment_entry

    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-verified-bridge-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=baseline,
            arm_id="baseline",
            run_group_id="verified-bridge-ledger-smoke",
            cwd=root,
        )
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=treatment,
            arm_id="treatment",
            run_group_id="verified-bridge-ledger-smoke",
            cwd=root,
        )
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["terminal-bench@2.0"]["cases"]["headless-terminal"]
        assert case["latest_decision"]["official_score_delta"] == 0.0, case
        assert case["latest_decision"]["baseline_failure_scope"] == "case_or_solution", case
        assert case["latest_decision"]["treatment_failure_scope"] == "case_or_solution", case
        assert case["latest_decision"]["decision"] == "paired_no_score_uplift", case
        assert case["latest_decision"]["case_routing"]["class"] == (
            "bridge_connected_no_uplift"
        ), case
        rendered = render_benchmark_run_ledger_markdown(ledger)
        assert "`bridge_connected_no_uplift`" in rendered, rendered


def test_repeated_case_timeout_routes_to_timeout_tier_candidate() -> None:
    baseline = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal_bench_2_0_make_doom_for_mips_codex_goal_mode_baseline",
        "mode": "codex_goal_mode_baseline",
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "failure_attribution_labels": ["agent_timeout_before_solution_completion"],
        "trials": [
            {
                "task_id": "make-doom-for-mips",
                "exception_type": "none",
            }
        ],
    }
    treatment = {
        **baseline,
        "job_name": "terminal_bench_2_0_make_doom_for_mips_codex_loopx_treatment",
        "mode": "codex_loopx",
        "loopx_inside_case": True,
    }

    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-timeout-tier-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=baseline,
            arm_id="baseline",
            run_group_id="timeout-tier-ledger-smoke",
            cwd=root,
        )
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=treatment,
            arm_id="treatment",
            run_group_id="timeout-tier-ledger-smoke",
            cwd=root,
        )
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["terminal-bench@2.0"]["cases"][
            "make-doom-for-mips"
        ]
        assert case["latest_decision"]["decision"] == (
            "paired_no_score_uplift_timeout_research_required"
        ), case
        assert case["latest_decision"]["case_routing"]["class"] == (
            "timeout_tier_policy_candidate"
        ), case
        assert case["latest_decision"]["case_routing"]["evidence"] == (
            "case_timeout_research_count=2"
        ), case


def test_passed_pair_routes_to_baseline_solved_non_regression() -> None:
    baseline = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "skillsbench@1.1",
        "job_name": "skillsbench_1_1_passed_pair_fixture_codex_acp_blind_loop_baseline",
        "mode": "skillsbench_codex_acp_blind_loop_baseline",
        "official_task_score": {
            "kind": "skillsbench_verifier_reward",
            "value": 1.0,
            "passed": True,
        },
        "score_failure_attribution": "none",
        "trials": [
            {
                "task_id": "passed-pair-fixture",
                "exception_type": "none",
            }
        ],
    }
    treatment = {
        **baseline,
        "job_name": "skillsbench_1_1_passed_pair_fixture_loopx_blind_loop_treatment",
        "mode": "skillsbench_loopx_blind_loop_treatment",
        "loopx_automation_loop": True,
    }
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-passed-pair-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=baseline,
            arm_id="baseline",
            run_group_id="passed-pair-ledger-smoke",
            cwd=root,
        )
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=treatment,
            arm_id="treatment",
            run_group_id="passed-pair-ledger-smoke",
            cwd=root,
        )
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "passed-pair-fixture"
        ]
        assert case["latest_decision"]["official_score_delta"] == 0.0, case
        assert case["latest_decision"]["baseline_failure_scope"] == "passed", case
        assert case["latest_decision"]["treatment_failure_scope"] == "passed", case
        assert case["latest_decision"]["decision"] == (
            "paired_baseline_solved_treatment_preserved"
        ), case


def stale_active_post_launch() -> dict[str, Any]:
    return {
        "schema_version": "terminal_bench_post_launch_materialization_v0",
        "checked": True,
        "ready_for_launch_state": True,
        "ready_for_compact_result_ingest": False,
        "ready_for_compact_failure_marker": True,
        "first_blocker": "stale_active_job_without_trial_result",
        "job_name": (
            "terminal_bench_multi_source_data_merger_codex_goal_mode_baseline_"
            "after_materialization_contract_20260615T092603CST"
        ),
        "jobs_dir_present": True,
        "job_root_present": True,
        "job_lock_present": True,
        "job_result_present": True,
        "job_result_finished": False,
        "job_active_without_trial_result": True,
        "job_stale_active_without_trial_result": True,
        "job_result_updated_at_present": True,
        "job_updated_age_seconds": 1393.584,
        "job_active_stale_seconds_threshold": 600,
        "job_running_trial_count": 1,
        "job_pending_trial_count": 0,
        "trial_result_present_count": 0,
        "compact_monitor_class": "stale_active_job_without_trial_result",
        "compact_failure_class": "stale_active_job_without_trial_result",
        "stale_active_reconcile_requested": True,
        "compact_failure_marker": {
            "schema_version": "terminal_bench_compact_failure_marker_v0",
            "failure_class": "stale_active_job_without_trial_result",
            "evidence_kind": "compact_stale_active_job_reconciliation",
            "external_handle_kind": "detached_worker_process",
            "external_handle_state": "ended",
            "external_handle_terminal": True,
            "terminal_closeout": True,
            "terminal_state": "terminal_compact_failure",
            "lifecycle_stage": "result_finalization",
            "ledger_attempt_kind": "runner_closeout_attempt",
            "runner_attempt_countable": True,
            "launch_state_countable": True,
            "case_attempt_countable": False,
            "benchmark_budget_countable": False,
            "next_allowed_action": "repair_result_finalization_closeout_contract_before_rerun",
            "job_result_present": True,
            "job_result_finished": False,
            "job_running_trial_count": 1,
            "job_pending_trial_count": 0,
            "job_result_updated_at_present": True,
            "job_updated_age_seconds": 1393.584,
            "job_active_stale_seconds_threshold": 600,
            "trial_result_present_count": 0,
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "raw_external_handle_payload_recorded": False,
            "attempt_accounting": {
                "schema_version": "benchmark_attempt_accounting_v0",
                "lifecycle_phase": "runner_accepted_args",
                "failure_label": "stale_active_job_without_trial_result",
                "failure_class": "job_materialization_failed",
                "attempts": {
                    "launcher": {"attempted": True, "countable": True},
                    "case": {"attempted": False, "countable": False},
                    "solver": {"attempted": False, "countable": False},
                    "verifier": {"attempted": False, "countable": False},
                    "official_score": {
                        "attempted": False,
                        "countable": False,
                    },
                },
                "launcher_attempt_countable": True,
                "case_attempt_countable": False,
                "solver_attempt_countable": False,
                "verifier_attempt_countable": False,
                "official_score_attempt_countable": False,
            },
        },
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
        "raw_external_handle_payload_recorded": False,
    }


def ended_active_post_launch() -> dict[str, Any]:
    payload = json.loads(json.dumps(stale_active_post_launch()))
    payload["first_blocker"] = "detached_worker_ended_active_without_trial_result"
    payload["job_stale_active_without_trial_result"] = False
    payload["job_updated_age_seconds"] = 42.0
    payload["compact_monitor_class"] = (
        "detached_worker_ended_active_without_trial_result"
    )
    payload["compact_failure_class"] = (
        "detached_worker_ended_active_without_trial_result"
    )
    marker = payload["compact_failure_marker"]
    marker["failure_class"] = "detached_worker_ended_active_without_trial_result"
    marker["evidence_kind"] = "detached_worker_active_job_without_trial_result"
    marker["job_updated_age_seconds"] = 42.0
    marker["attempt_accounting"]["failure_label"] = (
        "detached_worker_ended_active_without_trial_result"
    )
    return payload


def test_ledger_ingests_post_launch_stale_active_marker() -> None:
    compact = stale_active_post_launch()
    entry = build_benchmark_run_ledger_entry(
        compact,
        compact_artifact_ref=Path(".local/tmp/stale-active-post-launch.json"),
        run_group_id="stale-active-ledger-smoke",
        arm_id="codex_goal_mode_baseline",
        cwd=REPO_ROOT,
    )
    assert entry["benchmark_id"] == "terminal-bench@2.0", entry
    assert entry["case_id"] == "multi-source-data-merger", entry
    assert entry["status"] == "blocked", entry
    assert entry["score_status"] == "missing", entry
    assert entry["failure_class"] == "stale_active_job_without_trial_result", entry
    assert entry["failure_scope"] == "runner_or_setup", entry
    assert entry["repair_class"] == "runner_result_finalization", entry
    assert entry["source_event_schema"] == (
        "terminal_bench_post_launch_materialization_v0"
    ), entry
    assert entry["job_active_without_trial_result"] is True, entry
    assert entry["job_stale_active_without_trial_result"] is True, entry
    assert entry["compact_failure_evidence_kind"] == (
        "compact_stale_active_job_reconciliation"
    ), entry
    assert entry["ledger_attempt_kind"] == "runner_closeout_attempt", entry
    assert entry["terminal_closeout"] is True, entry
    assert entry["case_attempt_countable"] is False, entry
    assert entry["benchmark_budget_countable"] is False, entry
    assert entry["attempt_failure_class"] == "job_materialization_failed", entry
    assert entry["launcher_attempt_countable"] is True, entry
    assert entry["official_score_attempt_countable"] is False, entry

    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-stale-active-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            compact_artifact_ref=root / "post-launch.json",
            run_group_id="stale-active-ledger-smoke",
            arm_id="codex_goal_mode_baseline",
            cwd=root,
        )
        assert update["case_decision"]["decision"] == (
            "baseline_result_finalization_repair_required"
        ), update
        assert update["case_decision"]["repair_class"] == (
            "runner_result_finalization"
        ), update
        ledger = load_benchmark_run_ledger(ledger_path)
        rendered = render_benchmark_run_ledger_markdown(ledger)
        assert "runner_result_finalization" in rendered, rendered
        assert "stale_active_job_without_trial_result" in rendered, rendered
        assert "runner_closeout_attempt" in rendered, rendered


def test_ledger_ingests_post_launch_ended_active_marker() -> None:
    compact = ended_active_post_launch()
    entry = build_benchmark_run_ledger_entry(
        compact,
        compact_artifact_ref=Path(".local/tmp/ended-active-post-launch.json"),
        run_group_id="ended-active-ledger-smoke",
        arm_id="codex_goal_mode_baseline",
        cwd=REPO_ROOT,
    )
    assert entry["failure_class"] == (
        "detached_worker_ended_active_without_trial_result"
    ), entry
    assert entry["failure_scope"] == "runner_or_setup", entry
    assert entry["repair_class"] == "runner_result_finalization", entry
    assert entry["compact_failure_evidence_kind"] == (
        "detached_worker_active_job_without_trial_result"
    ), entry
    assert entry["ledger_attempt_kind"] == "runner_closeout_attempt", entry
    assert entry["terminal_closeout"] is True, entry
    assert entry["case_attempt_countable"] is False, entry
    assert entry["benchmark_budget_countable"] is False, entry
    assert (
        entry["attempt_failure_label"]
        == "detached_worker_ended_active_without_trial_result"
    ), entry
    assert entry["attempt_failure_class"] == "job_materialization_failed", entry
    assert entry["launcher_attempt_countable"] is True, entry
    assert entry["official_score_attempt_countable"] is False, entry


def test_cli_harbor_ingest_updates_run_ledger() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-cli-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        job_dir = write_goal_mode_model_access_failure_job(root)
        ledger_path = root / "visible-ledger.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run",
                "terminal-bench",
                "--goal-id",
                GOAL_ID,
                "--harbor-job-dir",
                str(job_dir),
                "--update-run-ledger",
                "--run-ledger-path",
                str(ledger_path),
                "--run-group-id",
                "ledger-cli-smoke",
                "--execute",
                "--no-global-sync",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["appended"] is True, payload
        ledger_payload = payload["benchmark_run_ledger"]
        assert ledger_payload["updated"] is True, ledger_payload
        assert ledger_payload["entry"]["case_id"] == "ledger-fixture", ledger_payload
        assert ledger_payload["case_decision"]["decision"] == (
            "baseline_model_access_repair_required"
        ), ledger_payload
        assert ledger_payload["case_decision"]["repair_class"] == (
            "runner_model_access"
        ), ledger_payload
        ledger = load_benchmark_run_ledger(ledger_path)
        assert ledger["schema_version"] == BENCHMARK_RUN_LEDGER_SCHEMA_VERSION, ledger
        assert (root / "visible-ledger.md").exists(), "CLI should render markdown"


def test_cli_compact_run_json_updates_run_ledger() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-compact-cli-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        ledger_path = root / "visible-ledger.json"
        compact_path = root / "compact-run.json"
        write_json(
            compact_path,
            {
                "schema_version": "benchmark_run_v0",
                "benchmark_id": "terminal-bench@2.0",
                "job_name": "terminal_bench_2_0_timeout_fixture_codex_goal_mode_baseline",
                "mode": "codex_goal_mode_baseline",
                "official_task_score": {
                    "kind": "harbor_verifier_reward",
                    "value": 0.0,
                    "passed": False,
                },
                "score_failure_attribution": "none",
                "trials": [
                    {
                        "task_id": "timeout-fixture",
                        "exception_type": "AgentTimeoutError",
                    }
                ],
            },
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run-ledger-upsert",
                "--benchmark-run-json",
                str(compact_path),
                "--run-ledger-path",
                str(ledger_path),
                "--run-group-id",
                "compact-ledger-cli-smoke",
                "--execute",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["read_boundary"]["raw_logs_read"] is False, payload
        ledger_payload = payload["benchmark_run_ledger"]
        assert ledger_payload["updated"] is True, ledger_payload
        assert ledger_payload["entry"]["case_id"] == "timeout-fixture", ledger_payload
        assert ledger_payload["entry"]["failure_class"] == (
            "agent_timeout_before_solution_completion"
        ), ledger_payload
        assert ledger_payload["case_decision"]["decision"] == (
            "baseline_failed_treatment_candidate"
        ), ledger_payload
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["terminal-bench@2.0"]["cases"]["timeout-fixture"]
        assert len(case["runs"]) == 1, case
        assert case["latest_decision"]["decision"] == (
            "baseline_failed_treatment_candidate"
        ), case
        assert (root / "visible-ledger.md").exists(), "CLI should render markdown"


def test_cli_run_ledger_check_reports_and_clears_history_drift() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-drift-cli-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        ledger_path = root / "visible-ledger.json"
        compact_path = root / "compact-run.json"
        write_json(
            compact_path,
            {
                "schema_version": "benchmark_run_v0",
                "benchmark_id": "terminal-bench@2.0",
                "job_name": "terminal_bench_2_0_drift_fixture_codex_goal_mode_baseline",
                "mode": "codex_goal_mode_baseline",
                "official_task_score": {
                    "kind": "harbor_verifier_reward",
                    "value": 0.0,
                    "passed": False,
                },
                "score_failure_attribution": "none",
                "trials": [
                    {
                        "task_id": "drift-fixture",
                        "exception_type": "AgentTimeoutError",
                    }
                ],
            },
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
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
                str(compact_path),
                "--execute",
                "--no-global-sync",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        check_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run-ledger-check",
                "--goal-id",
                GOAL_ID,
                "--run-ledger-path",
                str(ledger_path),
                "--history-limit",
                "20",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        check_payload = json.loads(check_result.stdout)
        drift = check_payload["benchmark_run_ledger_drift"]
        assert drift["schema_version"] == "benchmark_run_ledger_drift_v0", drift
        assert drift["drift_detected"] is True, drift
        assert drift["missing_ledger_run_count"] == 1, drift
        assert drift["missing_runs"][0]["case_id"] == "drift-fixture", drift
        assert drift["read_boundary"]["raw_logs_read"] is False, drift
        assert drift["read_boundary"]["trajectory_read"] is False, drift

        subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run-ledger-upsert",
                "--benchmark-run-json",
                str(compact_path),
                "--run-ledger-path",
                str(ledger_path),
                "--execute",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        clean_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run-ledger-check",
                "--goal-id",
                GOAL_ID,
                "--run-ledger-path",
                str(ledger_path),
                "--history-limit",
                "20",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        clean_payload = json.loads(clean_result.stdout)
        clean_drift = clean_payload["benchmark_run_ledger_drift"]
        assert clean_drift["drift_detected"] is False, clean_drift
        assert clean_drift["missing_ledger_run_count"] == 0, clean_drift
        assert clean_drift["matched_history_run_count"] == 1, clean_drift


def test_cli_post_launch_json_updates_run_ledger() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-post-launch-cli-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        ledger_path = root / "visible-ledger.json"
        post_launch_path = root / "post-launch.json"
        write_json(post_launch_path, stale_active_post_launch())
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run-ledger-upsert",
                "--post-launch-json",
                str(post_launch_path),
                "--run-ledger-path",
                str(ledger_path),
                "--run-group-id",
                "post-launch-ledger-cli-smoke",
                "--arm-id",
                "codex_goal_mode_baseline",
                "--execute",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["input_kind"] == (
            "terminal_bench_post_launch_materialization_v0"
        ), payload
        assert payload["read_boundary"]["raw_logs_read"] is False, payload
        ledger_payload = payload["benchmark_run_ledger"]
        assert ledger_payload["entry"]["case_id"] == "multi-source-data-merger", (
            ledger_payload
        )
        assert ledger_payload["entry"]["failure_class"] == (
            "stale_active_job_without_trial_result"
        ), ledger_payload
        assert ledger_payload["case_decision"]["decision"] == (
            "baseline_result_finalization_repair_required"
        ), ledger_payload
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["terminal-bench@2.0"]["cases"][
            "multi-source-data-merger"
        ]
        assert len(case["runs"]) == 1, case
        assert (root / "visible-ledger.md").exists(), "CLI should render markdown"


if __name__ == "__main__":
    test_ledger_entry_upsert_from_compact_run()
    test_ledger_classifies_compact_trial_exception_failure()
    test_ledger_classifies_setup_timeout_before_generic_timeout()
    test_ledger_routes_environment_setup_before_worker_separately()
    test_ledger_falls_back_to_terminal_bench_case_from_job_name()
    test_ledger_skips_running_result_placeholder()
    test_ledger_repair_backlog_uses_latest_run_per_arm()
    test_ledger_requires_attribution_for_zero_score_without_failure_signal()
    test_paired_runner_setup_blocker_overrides_zero_delta_no_uplift()
    test_verified_bridge_official_zero_routes_to_no_uplift_not_alignment()
    test_ledger_ingests_post_launch_stale_active_marker()
    test_ledger_ingests_post_launch_ended_active_marker()
    test_cli_harbor_ingest_updates_run_ledger()
    test_cli_compact_run_json_updates_run_ledger()
    test_cli_run_ledger_check_reports_and_clears_history_drift()
    test_cli_post_launch_json_updates_run_ledger()
    print("benchmark-run-ledger-smoke: ok")
