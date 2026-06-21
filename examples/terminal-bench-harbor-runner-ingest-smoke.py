#!/usr/bin/env python3
"""Smoke-test runner-side Terminal-Bench result ingestion with worker traces."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE,
    TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE,
    TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA,
    _iso_duration_seconds,
    build_terminal_bench_harbor_result_benchmark_run,
)
from loopx.status import (  # noqa: E402
    compact_benchmark_run,
    worker_bridge_ingest_health_note,
)

GOAL_ID = "terminal-bench-harbor-runner-ingest-fixture"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path, *, agent_timeout_multiplier: float | None = None) -> Path:
    suffix = (
        "agent_timeout_2x"
        if agent_timeout_multiplier is not None
        else "official_default_timeout"
    )
    job_dir = root / f"terminal_bench_sample_build_cython_ext_codex_loopx_active_e2e_{suffix}"
    trial_dir = job_dir / "build-cython-ext__sample"
    setup_failure_trial_dir = job_dir / "fix-code-vulnerability__setupfail"
    invocation = [
        "harbor",
        "run",
        "--dataset",
        "terminal-bench-sample@2.0",
        "--include-task-name",
        "build-cython-ext",
        "--agent-import-path",
        "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "--model",
        "gpt-5.5",
        "--agent-env",
        "CODEX_FORCE_AUTH_JSON=****",
        "--agent-kwarg",
        "loopx_mode=codex_loopx",
        "--agent-kwarg",
        "loopx_cli_bridge_enabled=true",
    ]
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
            "loopx_goal_id": "loopx-meta",
        },
    }
    write_json(
        job_dir / "lock.json",
        {
            "schema_version": 1,
            "invocation": invocation,
            "trials": [
                {
                    "task": {
                        "name": "build-cython-ext",
                        "source": "terminal-bench-sample",
                        "path": "sample/build-cython-ext",
                    },
                    "agent": agent,
                }
            ],
        },
    )
    timeout_config = {
        "timeout_multiplier": 1.0,
        "agent_timeout_multiplier": agent_timeout_multiplier,
        "verifier_timeout_multiplier": None,
        "agent_setup_timeout_multiplier": None,
        "environment_build_timeout_multiplier": None,
    }
    write_json(job_dir / "config.json", {"job_name": job_dir.name, **timeout_config})
    write_json(
        job_dir / "result.json",
        {
            "id": "job-id",
            "started_at": "2026-06-08T17:28:28Z",
            "updated_at": "2026-06-08T17:45:05Z",
            "finished_at": "2026-06-08T17:45:05Z",
            "n_total_trials": 2,
            "stats": {
                "n_completed_trials": 2,
                "n_errored_trials": 2,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
                "n_input_tokens": 5850995,
                "n_cache_tokens": 5667200,
                "n_output_tokens": 16946,
                "cost_usd": 4.260955,
            },
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "build-cython-ext",
            "trial_name": "build-cython-ext__sample",
            "source": "terminal-bench-sample",
            "config": {"agent": agent, **timeout_config},
            "agent_result": {
                "n_input_tokens": 5850995,
                "n_cache_tokens": 5667200,
                "n_output_tokens": 16946,
                "cost_usd": 4.260955,
            },
            "verifier_result": {"rewards": {"reward": 1.0}},
            "exception_info": {
                "exception_type": "AgentTimeoutError",
                "exception_message": "Agent execution timed out after 900.0 seconds",
            },
        },
    )
    write_json(
        setup_failure_trial_dir / "result.json",
        {
            "task_name": "fix-code-vulnerability",
            "trial_name": "fix-code-vulnerability__setupfail",
            "source": "terminal-bench-sample",
            "config": {"agent": agent, **timeout_config},
            "agent_result": {},
            "verifier_result": {"rewards": {}},
            "exception_info": {
                "exception_type": "NonZeroAgentExitCodeError",
                "exception_message": "Command failed (exit 127): setup command omitted",
            },
        },
    )
    (setup_failure_trial_dir / "agent" / "setup").mkdir(parents=True, exist_ok=True)
    (setup_failure_trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(setup_failure_trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "agent" / "trajectory.json").write_text("{}\n", encoding="utf-8")
    write_json(trial_dir / "agent" / "loopx-worker-benchmark-run.json", {"schema_version": "benchmark_run_v0"})
    trace_rows = [
        {"command": "status", "ok": True},
        {"command": "quota_should_run", "ok": True},
        {"command": "history", "ok": True},
        {"command": "check", "ok": True},
        {"command": "append_benchmark_run", "ok": False, "error_kind": "schema_rejected"},
        {"command": "append_benchmark_run", "ok": True, "dry_run": True},
    ]
    (trial_dir / "agent" / "loopx-counter-trace.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace_rows),
        encoding="utf-8",
    )
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("1.0\n", encoding="utf-8")
    (trial_dir / "verifier" / "test-stdout.txt").write_text(
        "benign platform probe: unknown platform bitness\n",
        encoding="utf-8",
    )
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_baseline_setup_diagnostic_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_baseline_setup_diagnostic"
    trial_dir = job_dir / "build-cython-ext__setupdiag"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_goal_mode_baseline",
            "loopx_access_packet_mode": (
                TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE
            ),
            "loopx_cli_bridge_enabled": False,
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
                "build-cython-ext",
            ],
            "trials": [
                {
                    "task": {
                        "name": "build-cython-ext",
                        "source": "terminal-bench-sample",
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
            "id": "job-id",
            "started_at": "2026-06-08T17:28:28Z",
            "updated_at": "2026-06-08T17:28:49Z",
            "finished_at": "2026-06-08T17:28:49Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
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
            "task_name": "build-cython-ext",
            "trial_name": "build-cython-ext__setupdiag",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {"exception_type": "NonZeroAgentExitCodeError"},
        },
    )
    (trial_dir / "agent" / "setup").mkdir(parents=True, exist_ok=True)
    write_json(
        trial_dir / "agent" / TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE,
        {
            "schema_version": TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA,
            "checkpoint_kind": "pre_worker_setup_probe",
            "interrupted": True,
            "first_blocker": "codex_cli_not_on_path",
            "pre_worker_startup_blocker": "codex_cli_not_on_path",
            "loopx_mode": "codex_goal_mode_baseline",
            "loopx_access_packet_mode": "none",
            "codex_install_strategy": "require_existing_codex",
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_recorded": False,
            "command_output_recorded": False,
        },
    )
    return job_dir


def write_worker_bridge_not_materialized_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_worker_bridge_not_materialized"
    trial_dir = job_dir / "build-cython-ext__bridge_missing"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
            "loopx_goal_id": "loopx-meta",
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
                "build-cython-ext",
                "--agent-import-path",
                "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
            ],
            "trials": [
                {
                    "task": {
                        "name": "build-cython-ext",
                        "source": "terminal-bench-sample",
                    },
                    "agent": agent,
                }
            ],
        },
    )
    write_json(
        job_dir / "config.json",
        {"job_name": job_dir.name},
    )
    write_json(
        job_dir / "result.json",
        {
            "started_at": "2026-06-09T05:00:00Z",
            "updated_at": "2026-06-09T05:03:10Z",
            "finished_at": "2026-06-09T05:03:10Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
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
            "task_name": "build-cython-ext",
            "trial_name": "build-cython-ext__bridge_missing",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {},
            "verifier_result": {"rewards": {}},
            "exception_info": {"exception_type": "RuntimeError"},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_agent_setup_timeout_before_worker_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_agent_setup_timeout_before_worker"
    trial_dir = job_dir / "large-scale-text-editing__setup_timeout"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
            "loopx_goal_id": "loopx-meta",
            "loopx_benchmark_run_json": (
                "/logs/agent/loopx-worker-benchmark-run.json"
            ),
            "loopx_counter_trace_json": (
                "/logs/agent/loopx-counter-trace.jsonl"
            ),
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
                "large-scale-text-editing",
                "--agent-import-path",
                "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
            ],
            "trials": [
                {
                    "task": {
                        "name": "large-scale-text-editing",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-09T05:00:00Z",
            "updated_at": "2026-06-09T05:24:29Z",
            "finished_at": "2026-06-09T05:24:29Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
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
            "task_name": "large-scale-text-editing",
            "trial_name": "large-scale-text-editing__setup_timeout",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {"exception_type": "AgentSetupTimeoutError"},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_worker_startup_blocker_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_worker_startup_blocker_recorded"
    trial_dir = job_dir / "large-scale-text-editing__startup_blocker"
    startup_blocker = "codex_cli_not_on_path"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
            "loopx_goal_id": "loopx-meta",
            "loopx_benchmark_run_json": (
                "/logs/agent/loopx-worker-benchmark-run.json"
            ),
            "loopx_counter_trace_json": (
                "/logs/agent/loopx-counter-trace.jsonl"
            ),
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
                "large-scale-text-editing",
                "--agent-import-path",
                "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
            ],
            "trials": [
                {
                    "task": {
                        "name": "large-scale-text-editing",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-09T05:00:00Z",
            "updated_at": "2026-06-09T05:03:10Z",
            "finished_at": "2026-06-09T05:03:10Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
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
            "task_name": "large-scale-text-editing",
            "trial_name": "large-scale-text-editing__startup_blocker",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {"exception_type": "NonZeroAgentExitCodeError"},
        },
    )
    write_json(
        trial_dir / "agent" / "loopx-worker-benchmark-run.json",
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "codex_worker",
            "mode": "codex_loopx",
            "real_run": True,
            "submit_eligible": False,
            "pre_worker_startup_blocker": startup_blocker,
            "first_blocker": startup_blocker,
            "repeat_blocked_by": startup_blocker,
            "worker_bridge_checkpoint": {
                "checkpoint_kind": "pre_worker_startup_blocker",
                "pre_worker_startup_blocker": startup_blocker,
            },
            "worker_bridge_outcome": {
                "schema_version": "worker_bridge_outcome_v0",
                "worker_bridge_verified": False,
                "pre_worker_startup_blocker": startup_blocker,
            },
            "validation": {
                "worker_startup_blocker_recorded": True,
                "runner_return_completed_or_blocker_recorded": True,
            },
        },
    )
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_environment_setup_failure_before_worker_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_environment_setup_before_worker"
    trial_dir = job_dir / "pytorch-model-recovery__env_setup_failed"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
            "loopx_goal_id": "loopx-meta",
            "loopx_benchmark_run_json": (
                "/logs/agent/loopx-worker-benchmark-run.json"
            ),
            "loopx_counter_trace_json": (
                "/logs/agent/loopx-counter-trace.jsonl"
            ),
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
                "pytorch-model-recovery",
                "--agent-import-path",
                "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
            ],
            "trials": [
                {
                    "task": {
                        "name": "pytorch-model-recovery",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-09T05:00:00Z",
            "updated_at": "2026-06-09T05:03:10Z",
            "finished_at": "2026-06-09T05:03:10Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
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
            "task_name": "pytorch-model-recovery",
            "trial_name": "pytorch-model-recovery__env_setup_failed",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "environment_setup": {
                "started_at": "2026-06-09T05:00:00Z",
                "finished_at": "2026-06-09T05:03:10Z",
            },
            "agent_setup": None,
            "agent_execution": None,
            "agent_result": None,
            "verifier_result": {"rewards": {}},
            "exception_info": {"exception_type": "RuntimeError"},
        },
    )
    return job_dir


def write_environment_setup_probe_materialized_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_mteb_retrieve_environment_setup_probe"
    trial_dir = job_dir / "mteb-retrieve__environment_setup_probe"
    agent = {"name": "nop"}
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
                "mteb-retrieve",
                "--agent",
                "nop",
                "--disable-verification",
            ],
            "trials": [
                {
                    "task": {
                        "name": "mteb-retrieve",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-09T05:00:00Z",
            "updated_at": "2026-06-09T05:03:10Z",
            "finished_at": "2026-06-09T05:03:10Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
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
            "task_name": "mteb-retrieve",
            "trial_name": "mteb-retrieve__environment_setup_probe",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "environment_setup": {
                "started_at": "2026-06-09T05:00:00Z",
                "finished_at": "2026-06-09T05:03:10Z",
            },
            "agent_setup": None,
            "agent_execution": None,
            "agent_result": None,
            "verifier_result": {"rewards": {}},
            "exception_info": {"exception_type": "RuntimeError"},
        },
    )
    return job_dir


def write_cli_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-08T00:00:00+00:00\n"
        "---\n\n"
        "# Terminal-Bench Harbor Runner Ingest Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Ingest the Harbor runner result fixture.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-08T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "loopx-platform",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "heartbeat": {
                        "enabled": True,
                    },
                }
            ],
        },
    )
    harbor_job_dir = write_fixture(root)
    return registry_path, runtime, harbor_job_dir


def run_cli_harbor_ingest_dry_run(root: Path) -> dict:
    registry_path, runtime, harbor_job_dir = write_cli_fixture(root)
    completed = subprocess.run(
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
            str(harbor_job_dir),
            "--no-global-sync",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict), payload
    return payload


def write_verifier_dependency_failure_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_verifier_dependency_failure"
    trial_dir = job_dir / "build-cython-ext__verifierfail"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
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
                "build-cython-ext",
            ],
            "trials": [
                {
                    "task": {
                        "name": "build-cython-ext",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-08T18:00:00Z",
            "updated_at": "2026-06-08T18:10:00Z",
            "finished_at": "2026-06-08T18:10:00Z",
            "n_total_trials": 1,
            "stats": {"n_completed_trials": 1, "n_errored_trials": 0},
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "build-cython-ext",
            "trial_name": "build-cython-ext__verifierfail",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {"n_input_tokens": 1200, "n_output_tokens": 100},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "agent" / "trajectory.json").write_text("{}\n", encoding="utf-8")
    write_json(
        trial_dir / "agent" / "loopx-worker-benchmark-run.json",
        {"schema_version": "benchmark_run_v0"},
    )
    (trial_dir / "agent" / "loopx-counter-trace.jsonl").write_text(
        json.dumps({"command": "status", "ok": True}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("0.0\n", encoding="utf-8")
    (trial_dir / "verifier" / "test-stdout.txt").write_text(
        "failed to download uv-x86_64-unknown-linux-gnu.tar.gz\n"
        "curl: (18) HTTP/2 stream was not closed cleanly\n"
        "uv: command not found\n",
        encoding="utf-8",
    )
    return job_dir


def write_verifier_platform_probe_failure_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_verifier_platform_probe_failure"
    trial_dir = job_dir / "make-mips-interpreter__platformfail"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
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
                "make-mips-interpreter",
            ],
            "trials": [
                {
                    "task": {
                        "name": "make-mips-interpreter",
                        "source": "terminal-bench",
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
            "started_at": "2026-06-08T18:20:00Z",
            "updated_at": "2026-06-08T18:30:00Z",
            "finished_at": "2026-06-08T18:30:00Z",
            "n_total_trials": 1,
            "stats": {"n_completed_trials": 1, "n_errored_trials": 0},
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "make-mips-interpreter",
            "trial_name": "make-mips-interpreter__platformfail",
            "source": "terminal-bench",
            "config": {"agent": agent},
            "agent_result": {"n_input_tokens": 1200, "n_output_tokens": 100},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "agent" / "trajectory.json").write_text("{}\n", encoding="utf-8")
    write_json(
        trial_dir / "agent" / "loopx-worker-benchmark-run.json",
        {
            "schema_version": "benchmark_run_v0",
            "submit_eligible": True,
            "leaderboard_evidence": False,
        },
    )
    (trial_dir / "agent" / "loopx-counter-trace.jsonl").write_text(
        json.dumps({"command": "check", "ok": True}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("0.0\n", encoding="utf-8")
    (trial_dir / "verifier" / "test-stdout.txt").write_text(
        "platform probe failed: unknown platform bitness\n",
        encoding="utf-8",
    )
    return job_dir


def write_worker_trace_timeout_writeback_loss_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_worker_trace_timeout_writeback_loss"
    trial_dir = job_dir / "qemu-alpine-ssh__timeout"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
            "loopx_active_user_intervention_enabled": True,
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
                "qemu-alpine-ssh",
            ],
            "trials": [
                {
                    "task": {
                        "name": "qemu-alpine-ssh",
                        "source": "terminal-bench",
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
            "started_at": "2026-06-08T19:20:00Z",
            "updated_at": "2026-06-08T19:39:40Z",
            "finished_at": "2026-06-08T19:39:40Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 1,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
                "n_input_tokens": 1665520,
                "n_cache_tokens": 1587456,
                "n_output_tokens": 7534,
                "cost_usd": 1.410068,
            },
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "qemu-alpine-ssh",
            "trial_name": "qemu-alpine-ssh__timeout",
            "source": "terminal-bench",
            "config": {"agent": agent},
            "agent_result": {
                "n_input_tokens": 1665520,
                "n_cache_tokens": 1587456,
                "n_output_tokens": 7534,
                "cost_usd": 1.410068,
            },
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {
                "exception_type": "AgentTimeoutError",
                "exception_message": "Agent execution timed out after 900.0 seconds",
            },
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "agent" / "trajectory.json").write_text("{}\n", encoding="utf-8")
    trace_rows = [
        {"command": "active_user_observe", "ok": True},
        {"command": "check", "ok": True},
    ]
    (trial_dir / "agent" / "loopx-counter-trace.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace_rows),
        encoding="utf-8",
    )
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("0.0\n", encoding="utf-8")
    (trial_dir / "verifier" / "test-stdout.txt").write_text(
        "platform probe failed: unknown platform bitness\n",
        encoding="utf-8",
    )
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_worker_self_validation_mismatch_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_worker_self_validation_mismatch"
    trial_dir = job_dir / "install-windows-3.11__mismatch"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
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
                "install-windows-3.11",
            ],
            "trials": [
                {
                    "task": {
                        "name": "install-windows-3.11",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-08T18:00:00Z",
            "updated_at": "2026-06-08T18:10:00Z",
            "finished_at": "2026-06-08T18:10:00Z",
            "n_total_trials": 1,
            "stats": {"n_completed_trials": 1, "n_errored_trials": 0},
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "install-windows-3.11",
            "trial_name": "install-windows-3.11__mismatch",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {"n_input_tokens": 1200, "n_output_tokens": 100},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    write_json(
        trial_dir / "agent" / "loopx-worker-benchmark-run.json",
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "loopx_managed_codex",
            "benchmark_id": "terminal-bench-sample@2.0",
            "job_name": "install-windows-3.11__mismatch",
            "mode": "codex_loopx",
            "worker_mode": "loopx_managed",
            "real_run": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "validation_scope": "worker_case_success",
            "case_success_claimed": True,
            "progress": {"completed": True},
            "validation": {
                "status": "passed",
                "validation_scope": "worker_case_success",
                "case_success_claimed": True,
                "checks": ["redacted"],
            },
            "trials": [{"task_id": "install-windows-3.11"}],
        },
    )
    trace_rows = [
        {"command": "check", "ok": True},
        {"command": "append_benchmark_run", "ok": True, "dry_run": True},
    ]
    (trial_dir / "agent" / "loopx-counter-trace.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace_rows),
        encoding="utf-8",
    )
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("0.0\n", encoding="utf-8")
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_worker_validation_scope_ambiguous_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_worker_validation_scope_ambiguous"
    trial_dir = job_dir / "install-windows-3.11__ambiguous"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
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
                "install-windows-3.11",
            ],
            "trials": [
                {
                    "task": {
                        "name": "install-windows-3.11",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-08T18:00:00Z",
            "updated_at": "2026-06-08T18:10:00Z",
            "finished_at": "2026-06-08T18:10:00Z",
            "n_total_trials": 1,
            "stats": {"n_completed_trials": 1, "n_errored_trials": 0},
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "install-windows-3.11",
            "trial_name": "install-windows-3.11__ambiguous",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {"n_input_tokens": 1200, "n_output_tokens": 100},
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    write_json(
        trial_dir / "agent" / "loopx-worker-benchmark-run.json",
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "loopx_managed_codex",
            "benchmark_id": "terminal-bench-sample@2.0",
            "job_name": "install-windows-3.11__ambiguous",
            "mode": "codex_loopx",
            "worker_mode": "loopx_managed",
            "real_run": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "progress": {"completed": True},
            "validation": {"status": "passed", "checks": ["redacted"]},
            "trials": [{"task_id": "install-windows-3.11"}],
        },
    )
    trace_rows = [
        {"command": "check", "ok": True},
        {"command": "append_benchmark_run", "ok": True, "dry_run": True},
    ]
    (trial_dir / "agent" / "loopx-counter-trace.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace_rows),
        encoding="utf-8",
    )
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("0.0\n", encoding="utf-8")
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_bare_codex_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_bare_codex_baseline"
    trial_dir = job_dir / "build-cython-ext__bare"
    agent = {"name": "codex", "model_name": "gpt-5.5", "kwargs": {}}
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
                "build-cython-ext",
                "--agent",
                "codex",
            ],
            "trials": [
                {
                    "task": {
                        "name": "build-cython-ext",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-08T19:00:00Z",
            "updated_at": "2026-06-08T19:12:00Z",
            "finished_at": "2026-06-08T19:12:00Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 0,
                "n_input_tokens": 1000,
                "n_cache_tokens": 600,
                "n_output_tokens": 200,
                "cost_usd": 0.2,
            },
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "build-cython-ext",
            "trial_name": "build-cython-ext__bare",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {
                "n_input_tokens": 1000,
                "n_cache_tokens": 600,
                "n_output_tokens": 200,
                "cost_usd": 0.2,
            },
            "verifier_result": {"rewards": {"reward": 1.0}},
            "exception_info": {},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "agent" / "trajectory.json").write_text("{}\n", encoding="utf-8")
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("1.0\n", encoding="utf-8")
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_clean_official_zero_fixture(root: Path) -> Path:
    job_dir = write_bare_codex_fixture(root)
    renamed = root / "terminal_bench_sample_clean_official_zero"
    job_dir.rename(renamed)
    trial_dir = renamed / "build-cython-ext__bare"

    job_result_path = renamed / "result.json"
    job_result = json.loads(job_result_path.read_text(encoding="utf-8"))
    job_result["stats"]["n_completed_trials"] = 1
    job_result["stats"]["n_errored_trials"] = 0
    write_json(job_result_path, job_result)

    trial_path = trial_dir / "result.json"
    trial = json.loads(trial_path.read_text(encoding="utf-8"))
    trial["verifier_result"] = {"rewards": {"reward": 0.0}}
    trial["exception_info"] = None
    trial.update(
        {
            "environment_setup": {
                "started_at": "2026-06-08T19:00:00Z",
                "finished_at": "2026-06-08T19:01:00Z",
            },
            "agent_setup": {
                "started_at": "2026-06-08T19:01:00Z",
                "finished_at": "2026-06-08T19:02:00Z",
            },
            "agent_execution": {
                "started_at": "2026-06-08T19:02:00Z",
                "finished_at": "2026-06-08T19:08:00Z",
            },
            "verifier": {
                "started_at": "2026-06-08T19:08:00Z",
                "finished_at": "2026-06-08T19:09:00Z",
            },
        }
    )
    write_json(trial_path, trial)
    (trial_dir / "verifier" / "reward.txt").write_text("0.0\n", encoding="utf-8")
    return renamed


def write_no_packet_runtime_goal_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_no_packet_runtime_goal_tools"
    trial_dir = job_dir / "build-cython-ext__nopacket"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_access_packet_mode": "none",
            "loopx_goal_id": "loopx-meta",
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
                "build-cython-ext",
                "--agent-import-path",
                "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
            ],
            "trials": [
                {
                    "task": {
                        "name": "build-cython-ext",
                        "source": "terminal-bench-sample",
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
            "started_at": "2026-06-09T04:00:00Z",
            "updated_at": "2026-06-09T04:14:52Z",
            "finished_at": "2026-06-09T04:14:52Z",
            "n_total_trials": 1,
            "stats": {
                "n_completed_trials": 1,
                "n_errored_trials": 0,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
                "n_input_tokens": 2272884,
                "n_cache_tokens": 2128512,
                "n_output_tokens": 10928,
                "cost_usd": 2.113956,
            },
        },
    )
    write_json(
        trial_dir / "result.json",
        {
            "task_name": "build-cython-ext",
            "trial_name": "build-cython-ext__nopacket",
            "source": "terminal-bench-sample",
            "config": {"agent": agent},
            "agent_result": {
                "n_input_tokens": 2272884,
                "n_cache_tokens": 2128512,
                "n_output_tokens": 10928,
                "cost_usd": 2.113956,
            },
            "verifier_result": {"rewards": {"reward": 1.0}},
            "exception_info": {},
        },
    )
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    write_json(
        trial_dir / "agent" / "trajectory.json",
        {
            "schema_version": "ATIF-v1.7",
            "steps": [
                {
                    "source": "agent",
                    "tool_calls": [
                        {
                            "function_name": "create_goal",
                            "arguments": {"objective": "redacted"},
                        }
                    ],
                },
                {
                    "source": "agent",
                    "tool_calls": [
                        {
                            "function_name": "update_goal",
                            "arguments": {"status": "complete"},
                        }
                    ],
                },
            ],
        },
    )
    (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
    (trial_dir / "verifier" / "reward.txt").write_text("1.0\n", encoding="utf-8")
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def write_codex_goal_mode_baseline_fixture(root: Path) -> Path:
    source_dir = write_no_packet_runtime_goal_fixture(root)
    job_dir = root / "terminal_bench_sample_codex_goal_mode_baseline"
    source_dir.rename(job_dir)

    def read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def rewrite_agent(agent: dict) -> dict:
        updated = dict(agent)
        kwargs = dict(updated.get("kwargs") or {})
        kwargs["loopx_mode"] = "codex_goal_mode_baseline"
        kwargs["loopx_ablation_mode"] = "codex_goal_mode_baseline"
        kwargs["loopx_access_packet_mode"] = "none"
        updated["kwargs"] = kwargs
        return updated

    lock_path = job_dir / "lock.json"
    lock = read_json(lock_path)
    lock["trials"][0]["agent"] = rewrite_agent(lock["trials"][0]["agent"])
    write_json(lock_path, lock)

    config_path = job_dir / "config.json"
    config = read_json(config_path)
    config["job_name"] = job_dir.name
    write_json(config_path, config)

    trial_path = job_dir / "build-cython-ext__nopacket" / "result.json"
    trial = read_json(trial_path)
    trial["config"]["agent"] = rewrite_agent(trial["config"]["agent"])
    write_json(trial_path, trial)
    return job_dir


def write_partial_harbor_stats_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_partial_harbor_stats"
    agent = {
        "import_path": "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "loopx_mode": "codex_loopx",
            "loopx_cli_bridge_enabled": True,
        },
    }
    write_json(
        job_dir / "lock.json",
        {
            "schema_version": 1,
            "invocation": [
                "harbor",
                "run",
                "--path",
                "terminal-bench-sample-gh-e2e-subset",
                "--agent-import-path",
                "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
            ],
            "trials": [
                {
                    "task": {
                        "name": "build-cython-ext",
                        "source": "terminal-bench-sample-gh-e2e-subset",
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
            "started_at": "2026-06-08T20:00:00Z",
            "updated_at": "2026-06-08T20:13:00Z",
            "finished_at": "2026-06-08T20:13:00Z",
            "n_total_trials": 3,
            "stats": {
                "n_completed_trials": 3,
                "n_errored_trials": 1,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
                "evals": {
                    "loopx-managed-codex__gpt-5.5__sample": {
                        "n_trials": 2,
                        "n_errors": 1,
                        "metrics": [{"mean": 2 / 3}],
                        "reward_stats": {
                            "reward": {
                                "1.0": [
                                    "fix-code-vulnerability__partial",
                                    "regex-log__partial",
                                ]
                            }
                        },
                        "exception_stats": {
                            "NonZeroAgentExitCodeError": [
                                "build-cython-ext__partial"
                            ]
                        },
                    }
                },
                "n_input_tokens": 3000,
                "n_cache_tokens": 1800,
                "n_output_tokens": 600,
                "cost_usd": 0.6,
            },
        },
    )
    trial_specs = [
        ("build-cython-ext", "build-cython-ext__partial", None, "NonZeroAgentExitCodeError"),
        ("fix-code-vulnerability", "fix-code-vulnerability__partial", 1.0, None),
        ("regex-log", "regex-log__partial", 1.0, None),
    ]
    for task_id, trial_name, reward, exception_type in trial_specs:
        trial_dir = job_dir / trial_name
        rewards = {} if reward is None else {"reward": reward}
        write_json(
            trial_dir / "result.json",
            {
                "task_name": task_id,
                "trial_name": trial_name,
                "source": "terminal-bench-sample-gh-e2e-subset",
                "config": {"agent": agent},
                "agent_result": {
                    "n_input_tokens": 1000,
                    "n_cache_tokens": 600,
                    "n_output_tokens": 200,
                    "cost_usd": 0.2,
                }
                if reward is not None
                else {},
                "verifier_result": {"rewards": rewards},
                "exception_info": (
                    {"exception_type": exception_type}
                    if exception_type is not None
                    else {}
                ),
            },
        )
        (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
        write_json(
            trial_dir / "agent" / "loopx-worker-benchmark-run.json",
            {"schema_version": "benchmark_run_v0"},
        )
        if reward is not None:
            (trial_dir / "agent" / "loopx-counter-trace.jsonl").write_text(
                json.dumps({"command": "status", "ok": True}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (trial_dir / "verifier").mkdir(parents=True, exist_ok=True)
            (trial_dir / "verifier" / "reward.txt").write_text(
                f"{reward}\n", encoding="utf-8"
            )
        (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        write_json(trial_dir / "artifacts" / "manifest.json", {"files": ["redacted"]})
    return job_dir


def assert_public_safe(payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/Users/",
        "OPENAI_API_KEY",
        "CODEX_FORCE_AUTH_JSON=sk-",
        "auth.json",
        "sessions/",
        "exception_traceback",
        "failed to download",
        "curl: (18)",
        "uv-x86_64-unknown-linux-gnu.tar.gz",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def main() -> None:
    assert _iso_duration_seconds(
        "2026-06-10T17:50:00",
        "2026-06-10T17:50:03+00:00",
    ) == 3.0

    with tempfile.TemporaryDirectory(prefix="loopx-harbor-runner-ingest-") as tmp:
        payload = build_terminal_bench_harbor_result_benchmark_run(write_fixture(Path(tmp)))

    assert payload["schema_version"] == "benchmark_run_v0", payload
    assert payload["source_runner"] == "harbor", payload
    assert payload["benchmark_id"] == "terminal-bench-sample@2.0", payload
    assert payload["mode"] == "codex_loopx", payload
    assert payload["loopx_inside_case"] is True, payload
    assert payload["worker_loopx_cli_call_total"] == 6, payload
    assert payload["worker_counter_trace_trial_count"] == 1, payload
    assert payload["worker_benchmark_run_file_count"] == 1, payload
    assert payload["worker_benchmark_run_schema_ok_count"] == 1, payload
    assert payload.get("worker_setup_diagnostic_file_count", 0) == 0, payload
    assert payload.get("worker_setup_diagnostic_schema_ok_count", 0) == 0, payload
    assert payload["worker_submit_eligible_mismatch_count"] == 0, payload
    assert payload["worker_bridge_materialization_status"] == "verified", payload
    assert payload["worker_bridge_materialization_blocker"] == "none", payload
    assert payload["repeat_blocked_by"] == "none", payload
    assert (
        payload["worker_submit_eligible_mismatch_reason"] == "none"
    ), payload
    assert payload["pre_worker_agent_setup_failure_count"] == 1, payload
    assert payload["interaction_counters"]["loopx_cli_calls"]["append_benchmark_run"] == 2, payload
    assert payload["interaction_counters"]["append_benchmark_run_success_count"] == 1, payload
    assert payload["interaction_counters"]["append_benchmark_run_schema_rejected_count"] == 1, payload
    assert payload["interaction_counters"]["worker_counter_trace_trial_count"] == 1, payload
    assert payload["interaction_counters"]["worker_benchmark_run_file_count"] == 1, payload
    assert payload["interaction_counters"]["worker_benchmark_run_schema_ok_count"] == 1, payload
    assert payload["interaction_counters"].get("worker_setup_diagnostic_file_count", 0) == 0, payload
    assert payload["interaction_counters"].get("worker_setup_diagnostic_schema_ok_count", 0) == 0, payload
    assert payload["interaction_counters"]["worker_submit_eligible_mismatch_count"] == 0, payload
    assert (
        payload["interaction_counters"]["worker_submit_eligible_mismatch_reason"]
        == "none"
    ), payload
    assert payload["interaction_counters"]["pre_worker_agent_setup_failure_count"] == 1, payload
    assert payload["interaction_counters"]["case_result_writeback"] == "worker_bridge_append_benchmark_run_dry_run", payload
    overhead = payload["overhead_attribution_counters"]
    assert (
        overhead["schema_version"]
        == "terminal_bench_overhead_attribution_counters_v0"
    ), overhead
    assert overhead["raw_logs_read"] is False, overhead
    assert overhead["raw_trace_recorded"] is False, overhead
    assert overhead["raw_task_prompt_recorded"] is False, overhead
    assert overhead["attribution_granularity"] == "coarse_worker_bridge_event_counts", overhead
    assert (
        overhead["worker_step_counter_status"]
        == "worker_cli_counter_trace_present_no_phase_breakdown"
    ), overhead
    assert overhead["wall_time_seconds"] == 997.0, overhead
    assert overhead["input_tokens"] == 5850995, overhead
    assert overhead["worker_bridge_event_count"] == 6, overhead
    assert overhead["loopx_cli_call_total"] == 6, overhead
    assert overhead["loopx_required_cli_call_total"] == 3, overhead
    assert overhead["loopx_optional_context_cli_call_total"] == 3, overhead
    assert overhead["append_benchmark_run_success_count"] == 1, overhead
    assert overhead["worker_submit_eligible_mismatch_count"] == 0, overhead
    assert overhead["worker_submit_eligible_mismatch_reason"] == "none", overhead
    assert payload["official_task_score"]["value"] == 1.0, payload
    assert payload["official_score"] == 1.0, payload
    assert (
        payload["official_score_source"]
        == payload["official_task_score"]["source"]
    ), payload
    assert payload["official_score_status"] == "completed", payload
    assert payload["runner_return_status"] == "completed_with_agent_timeout", payload
    assert payload["progress"]["n_errored_trials"] == 2, payload
    assert payload["trials"][0]["exception_type"] == "AgentTimeoutError", payload
    passed_trial = next(trial for trial in payload["trials"] if trial["task_id"] == "build-cython-ext")
    assert "verifier_failure_attribution" not in passed_trial, passed_trial
    assert payload["verifier_dependency_failure_count"] == 0, payload
    setup_trial = next(
        trial for trial in payload["trials"] if trial["task_id"] == "fix-code-vulnerability"
    )
    assert setup_trial["worker_start_status"] == "pre_worker_agent_setup_failed", setup_trial
    with tempfile.TemporaryDirectory(prefix="loopx-baseline-setup-diag-") as tmp:
        baseline_setup_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_baseline_setup_diagnostic_fixture(Path(tmp))
        )
    assert baseline_setup_payload["mode"] == "codex_goal_mode_baseline", baseline_setup_payload
    assert baseline_setup_payload["worker_setup_diagnostic_file_count"] == 1, baseline_setup_payload
    assert baseline_setup_payload["worker_setup_diagnostic_schema_ok_count"] == 1, baseline_setup_payload
    assert baseline_setup_payload["worker_startup_blocker_count"] == 1, baseline_setup_payload
    assert baseline_setup_payload["worker_startup_blockers"] == [
        "codex_cli_not_on_path"
    ], baseline_setup_payload
    assert baseline_setup_payload["worker_setup_diagnostic_blockers"] == [
        "codex_cli_not_on_path"
    ], baseline_setup_payload
    assert "codex_cli_not_on_path" in baseline_setup_payload[
        "failure_attribution_labels"
    ], baseline_setup_payload
    baseline_setup_trial = baseline_setup_payload["trials"][0]
    assert (
        baseline_setup_trial["worker_setup_diagnostic_blocker"]
        == "codex_cli_not_on_path"
    ), baseline_setup_trial
    baseline_setup_compact = compact_benchmark_run(baseline_setup_payload)
    assert baseline_setup_compact["worker_setup_diagnostic_file_count"] == 1, baseline_setup_compact
    assert baseline_setup_compact["worker_setup_diagnostic_schema_ok_count"] == 1, baseline_setup_compact
    assert baseline_setup_compact["worker_startup_blockers"] == [
        "codex_cli_not_on_path"
    ], baseline_setup_compact
    assert baseline_setup_compact["worker_setup_diagnostic_blockers"] == [
        "codex_cli_not_on_path"
    ], baseline_setup_compact
    assert_public_safe(baseline_setup_payload)
    assert_public_safe(baseline_setup_compact)
    assert payload["worker_bridge_outcome"]["runner_return_status"] == "completed_with_agent_timeout", payload
    assert payload["worker_bridge_outcome"]["pre_worker_agent_setup_failure_count"] == 1, payload
    assert (
        payload["worker_bridge_outcome"]["worker_bridge_materialization_status"]
        == "verified"
    ), payload
    assert (
        payload["worker_bridge_outcome"]["repeat_blocked_by"] == "none"
    ), payload
    episode_policy = payload["episode_policy"]
    assert (
        episode_policy["mode"] == "single_codex_agent_loopx_assisted_checkpoints"
    ), episode_policy
    assert episode_policy["worker_topology"] == "single_codex_agent", episode_policy
    assert episode_policy["runner_side_guaranteed_writeback"] is True, episode_policy
    assert episode_policy["does_not_spawn_additional_agents"] is True, episode_policy
    policy = payload["worker_bridge_outcome"]["wall_time_policy"]
    assert policy["timeout_tier"] == "official_default_agent_timeout_900s", policy
    assert policy["changes_official_benchmark_timeout"] is False, policy
    assert policy["official_timeout_comparable"] is True, policy
    assert policy["wall_time_limit_seconds"] == 900.0, policy
    assert policy["true_long_task_bar_seconds"] == 1800.0, policy
    assert policy["observed_true_long_task_bar_met"] is False, policy
    assert policy["expected_true_long_task_bar_met"] is False, policy
    assert policy["true_long_task_bar_met"] is False, policy
    assert payload["worker_bridge_outcome"]["runner_side_writeback_guaranteed"] is True, payload
    assert (
        payload["worker_bridge_outcome"]["worker_submit_eligible_mismatch_observed"]
        is False
    ), payload
    assert (
        payload["validation"]["worker_submit_eligible_matches_runner_boundary"]
        is True
    ), payload
    compact = compact_benchmark_run(payload)
    assert compact and compact["worker_loopx_cli_call_total"] == 6, compact
    assert compact["worker_counter_trace_trial_count"] == 1, compact
    assert compact["worker_benchmark_run_file_count"] == 1, compact
    assert compact["worker_benchmark_run_schema_ok_count"] == 1, compact
    assert compact["worker_submit_eligible_mismatch_count"] == 0, compact
    assert compact["worker_bridge_materialization_status"] == "verified", compact
    assert compact["worker_bridge_materialization_blocker"] == "none", compact
    assert compact["repeat_blocked_by"] == "none", compact
    assert compact["worker_submit_eligible_mismatch_reason"] == "none", compact
    assert compact["pre_worker_agent_setup_failure_count"] == 1, compact
    assert compact["interaction_counters"]["append_benchmark_run_success_count"] == 1, compact
    assert compact["interaction_counters"]["append_benchmark_run_schema_rejected_count"] == 1, compact
    assert compact["interaction_counters"]["pre_worker_agent_setup_failure_count"] == 1, compact
    compact_overhead = compact["overhead_attribution_counters"]
    assert compact_overhead["raw_logs_read"] is False, compact_overhead
    assert compact_overhead["raw_trace_recorded"] is False, compact_overhead
    assert (
        compact_overhead["attribution_granularity"]
        == "coarse_worker_bridge_event_counts"
    ), compact_overhead
    assert compact_overhead["loopx_cli_call_total"] == 6, compact_overhead
    assert compact_overhead["worker_bridge_event_count"] == 6, compact_overhead
    assert compact_overhead["worker_submit_eligible_mismatch_count"] == 0, compact_overhead
    assert compact["trials"][0]["exception_type"] == "AgentTimeoutError", compact
    compact_setup_trial = next(
        trial for trial in compact["trials"] if trial["task_id"] == "fix-code-vulnerability"
    )
    assert compact_setup_trial["worker_start_status"] == "pre_worker_agent_setup_failed", compact
    assert compact["official_task_score"]["passed"] is True, compact
    assert (
        compact["episode_policy"]["mode"]
        == "single_codex_agent_loopx_assisted_checkpoints"
    ), compact
    assert compact["episode_policy"]["does_not_change_task_solution_actor"] is True, compact
    compact_policy = compact["worker_bridge_outcome"]["wall_time_policy"]
    assert compact_policy["timeout_tier"] == "official_default_agent_timeout_900s", compact_policy
    assert compact_policy["changes_official_benchmark_timeout"] is False, compact_policy
    assert compact_policy["wall_time_limit_seconds"] == 900.0, compact_policy
    assert compact_policy["true_long_task_bar_seconds"] == 1800.0, compact_policy
    assert compact_policy["observed_true_long_task_bar_met"] is False, compact_policy
    assert compact_policy["expected_true_long_task_bar_met"] is False, compact_policy
    assert compact_policy["true_long_task_bar_met"] is False, compact_policy
    assert compact["worker_bridge_outcome"]["runner_side_writeback_guaranteed"] is True, compact
    assert (
        compact["worker_bridge_outcome"]["worker_bridge_materialization_status"]
        == "verified"
    ), compact
    assert_public_safe(payload)
    assert_public_safe(compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-bridge-not-materialized-") as tmp:
        bridge_missing_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_worker_bridge_not_materialized_fixture(Path(tmp))
        )
    assert (
        bridge_missing_payload["worker_bridge_materialization_status"]
        == "runtime_exception_before_checkpoint"
    ), bridge_missing_payload
    assert (
        bridge_missing_payload["worker_bridge_materialization_blocker"]
        == "worker_runtime_exception_before_bridge_checkpoint"
    ), bridge_missing_payload
    assert (
        bridge_missing_payload["worker_bridge_failure_attribution"]
        == "worker_runtime_exception_before_bridge_checkpoint"
    ), bridge_missing_payload
    assert (
        bridge_missing_payload["first_blocker"]
        == "worker_runtime_exception_before_bridge_checkpoint"
    ), bridge_missing_payload
    assert (
        bridge_missing_payload["repeat_blocked_by"]
        == "worker_runtime_exception_before_bridge_checkpoint"
    ), bridge_missing_payload
    assert (
        bridge_missing_payload["worker_runtime_exception_before_checkpoint_count"]
        == 1
    ), bridge_missing_payload
    assert (
        bridge_missing_payload["validation"]["worker_bridge_materialized_when_required"]
        is False
    ), bridge_missing_payload
    assert bridge_missing_payload["validation"]["worker_bridge_repeat_ready"] is False, bridge_missing_payload
    assert (
        bridge_missing_payload["worker_bridge_outcome"]["next_action"]
        == "diagnose compact worker runtime failure before another repeat"
    ), bridge_missing_payload
    bridge_missing_compact = compact_benchmark_run(bridge_missing_payload)
    bridge_missing_health = worker_bridge_ingest_health_note(bridge_missing_compact)
    assert (
        bridge_missing_compact["worker_bridge_materialization_status"]
        == "runtime_exception_before_checkpoint"
    ), bridge_missing_compact
    assert (
        bridge_missing_compact["worker_bridge_outcome"][
            "worker_bridge_materialization_blocker"
        ]
        == "worker_runtime_exception_before_bridge_checkpoint"
    ), bridge_missing_compact
    assert (
        bridge_missing_compact["worker_bridge_failure_attribution"]
        == "worker_runtime_exception_before_bridge_checkpoint"
    ), bridge_missing_compact
    assert (
        bridge_missing_compact["validation"]["worker_bridge_materialized_when_required"]
        is False
    ), bridge_missing_compact
    assert bridge_missing_compact["validation"]["worker_bridge_repeat_ready"] is False, bridge_missing_compact
    assert (
        bridge_missing_health["health_state"]
        == "worker_runtime_exception_before_bridge_checkpoint"
    ), bridge_missing_health
    assert (
        bridge_missing_health["next_action"]
        == "diagnose compact worker runtime failure before another run"
    ), bridge_missing_health
    assert_public_safe(bridge_missing_payload)
    assert_public_safe(bridge_missing_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-agent-setup-timeout-") as tmp:
        setup_timeout_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_agent_setup_timeout_before_worker_fixture(Path(tmp))
        )
    assert (
        setup_timeout_payload["worker_bridge_materialization_status"]
        == "pre_worker_setup_failed"
    ), setup_timeout_payload
    assert (
        setup_timeout_payload["worker_bridge_materialization_blocker"]
        == "pre_worker_agent_setup_failed_before_bridge_checkpoint"
    ), setup_timeout_payload
    assert setup_timeout_payload["pre_worker_agent_setup_failure_count"] == 1, setup_timeout_payload
    assert (
        setup_timeout_payload["worker_runtime_exception_before_checkpoint_count"] == 0
    ), setup_timeout_payload
    assert setup_timeout_payload["score_failure_attribution"] == (
        "agent_setup_timeout_score_failure"
    ), setup_timeout_payload
    assert "agent_setup_timeout_before_worker_start" in setup_timeout_payload[
        "failure_attribution_labels"
    ], setup_timeout_payload
    setup_timeout_trial = setup_timeout_payload["trials"][0]
    assert (
        setup_timeout_trial["worker_start_status"]
        == "pre_worker_agent_setup_failed"
    ), setup_timeout_trial
    assert (
        setup_timeout_payload["worker_bridge_outcome"]["runner_return_status"]
        == "completed_with_agent_setup_timeout"
    ), setup_timeout_payload
    assert (
        setup_timeout_payload["worker_bridge_outcome"]["next_action"]
        == "repair Codex agent setup/launcher before another same-task repeat"
    ), setup_timeout_payload
    setup_timeout_compact = compact_benchmark_run(setup_timeout_payload)
    setup_timeout_health = worker_bridge_ingest_health_note(setup_timeout_compact)
    assert (
        setup_timeout_payload["runner_return_status"]
        == setup_timeout_payload["worker_bridge_outcome"]["runner_return_status"]
    ), setup_timeout_payload
    assert setup_timeout_payload["official_score_status"] == "completed", setup_timeout_payload
    assert setup_timeout_payload["official_score"] == 0.0, setup_timeout_payload
    assert (
        setup_timeout_compact["worker_bridge_materialization_status"]
        == "pre_worker_setup_failed"
    ), setup_timeout_compact
    assert setup_timeout_compact["runner_return_status"] == (
        "completed_with_agent_setup_timeout"
    ), setup_timeout_compact
    assert setup_timeout_compact["official_score_status"] == "completed", setup_timeout_compact
    assert setup_timeout_compact["official_score"] == 0.0, setup_timeout_compact
    assert (
        setup_timeout_compact["score_failure_attribution"]
        == "agent_setup_timeout_score_failure"
    ), setup_timeout_compact
    assert (
        setup_timeout_health["health_state"]
        == "pre_worker_agent_setup_failed_before_bridge_checkpoint"
    ), setup_timeout_health
    assert_public_safe(setup_timeout_payload)
    assert_public_safe(setup_timeout_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-startup-blocker-") as tmp:
        startup_blocker_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_worker_startup_blocker_fixture(Path(tmp))
        )
    assert (
        startup_blocker_payload["worker_bridge_materialization_status"]
        == "pre_worker_startup_blocker_recorded"
    ), startup_blocker_payload
    assert (
        startup_blocker_payload["worker_bridge_materialization_blocker"]
        == "codex_cli_not_on_path"
    ), startup_blocker_payload
    assert (
        startup_blocker_payload["worker_bridge_failure_attribution"]
        == "codex_cli_not_on_path"
    ), startup_blocker_payload
    assert startup_blocker_payload["score_failure_attribution"] == (
        "agent_setup_score_failure"
    ), startup_blocker_payload
    assert "pre_worker_startup_blocker_recorded" in startup_blocker_payload[
        "failure_attribution_labels"
    ], startup_blocker_payload
    assert (
        startup_blocker_payload["first_blocker"]
        == "codex_cli_not_on_path"
    ), startup_blocker_payload
    assert (
        startup_blocker_payload["repeat_blocked_by"]
        == "codex_cli_not_on_path"
    ), startup_blocker_payload
    assert startup_blocker_payload["pre_worker_startup_blocker"] == (
        "codex_cli_not_on_path"
    ), startup_blocker_payload
    assert startup_blocker_payload["worker_startup_blocker_count"] == 1, startup_blocker_payload
    assert startup_blocker_payload["worker_loopx_cli_call_total"] == 0, startup_blocker_payload
    assert startup_blocker_payload["worker_counter_trace_trial_count"] == 0, startup_blocker_payload
    assert startup_blocker_payload["worker_benchmark_run_file_count"] == 1, startup_blocker_payload
    assert startup_blocker_payload["worker_benchmark_run_schema_ok_count"] == 1, startup_blocker_payload
    assert (
        startup_blocker_payload["validation"]["worker_bridge_materialized_when_required"]
        is True
    ), startup_blocker_payload
    assert startup_blocker_payload["validation"]["worker_bridge_repeat_ready"] is False, startup_blocker_payload
    assert (
        startup_blocker_payload["worker_bridge_outcome"]["next_action"]
        == "repair recorded worker startup blocker before another same-task repeat"
    ), startup_blocker_payload
    assert (
        startup_blocker_payload["worker_bridge_outcome"]["pre_worker_startup_blocker"]
        == "codex_cli_not_on_path"
    ), startup_blocker_payload
    startup_blocker_compact = compact_benchmark_run(startup_blocker_payload)
    startup_blocker_health = worker_bridge_ingest_health_note(startup_blocker_compact)
    assert startup_blocker_payload["runner_return_status"] == "completed", startup_blocker_payload
    assert startup_blocker_payload["official_score_status"] == "completed", startup_blocker_payload
    assert startup_blocker_payload["official_score"] == 0.0, startup_blocker_payload
    assert (
        startup_blocker_compact["worker_bridge_materialization_status"]
        == "pre_worker_startup_blocker_recorded"
    ), startup_blocker_compact
    assert startup_blocker_compact["runner_return_status"] == "completed", startup_blocker_compact
    assert startup_blocker_compact["official_score_status"] == "completed", startup_blocker_compact
    assert startup_blocker_compact["official_score"] == 0.0, startup_blocker_compact
    assert startup_blocker_compact["worker_startup_blocker_count"] == 1, startup_blocker_compact
    assert startup_blocker_compact["score_failure_attribution"] == (
        "agent_setup_score_failure"
    ), startup_blocker_compact
    assert "pre_worker_startup_blocker_recorded" in startup_blocker_compact[
        "failure_attribution_labels"
    ], startup_blocker_compact
    assert startup_blocker_compact["pre_worker_startup_blocker"] == (
        "codex_cli_not_on_path"
    ), startup_blocker_compact
    assert (
        startup_blocker_compact["worker_bridge_outcome"]["pre_worker_startup_blocker"]
        == "codex_cli_not_on_path"
    ), startup_blocker_compact
    assert (
        startup_blocker_health["health_state"]
        == "codex_cli_not_on_path"
    ), startup_blocker_health
    assert (
        startup_blocker_health["evidence_layer"] == "compact_startup_blocker"
    ), startup_blocker_health
    assert (
        startup_blocker_health["next_action"]
        == "repair recorded worker startup blocker before another run"
    ), startup_blocker_health
    assert_public_safe(startup_blocker_payload)
    assert_public_safe(startup_blocker_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-env-setup-failed-") as tmp:
        env_setup_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_environment_setup_failure_before_worker_fixture(Path(tmp))
        )
    assert (
        env_setup_payload["worker_bridge_materialization_status"]
        == "environment_setup_failed_before_worker"
    ), env_setup_payload
    assert (
        env_setup_payload["worker_bridge_materialization_blocker"]
        == "environment_setup_failed_before_worker"
    ), env_setup_payload
    assert (
        env_setup_payload["worker_bridge_failure_attribution"]
        == "environment_setup_failed_before_worker"
    ), env_setup_payload
    assert (
        env_setup_payload["environment_setup_failure_before_worker_count"] == 1
    ), env_setup_payload
    assert (
        env_setup_payload["worker_runtime_exception_before_checkpoint_count"] == 0
    ), env_setup_payload
    assert (
        env_setup_payload["trials"][0]["worker_start_status"]
        == "environment_setup_failed_before_worker"
    ), env_setup_payload
    assert (
        env_setup_payload["worker_bridge_outcome"]["next_action"]
        == "diagnose benchmark environment setup before worker startup"
    ), env_setup_payload
    env_context = env_setup_payload["environment_setup_failure_context"]
    assert env_context["surface"] == "harbor_environment_setup", env_context
    assert (
        env_context["failure_kind"]
        == "environment_setup_runtime_error_before_worker"
    ), env_context
    assert (
        env_context["diagnostic_granularity"] == "phase_fields_only_no_raw_logs"
    ), env_context
    assert env_context["exception_type"] == "RuntimeError", env_context
    assert env_context["timeout_signal"] == "no_timeout_exception_type", env_context
    assert (
        env_context["resource_signal"] == "not_observable_from_phase_fields"
    ), env_context
    assert env_context["environment_setup_started"] is True, env_context
    assert env_context["environment_setup_finished"] is True, env_context
    assert env_context["agent_setup_started"] is False, env_context
    assert env_context["agent_execution_started"] is False, env_context
    assert env_context["environment_setup_duration_seconds"] == 190.0, env_context
    assert (
        env_context["environment_setup_duration_tier"] == "three_to_ten_minutes"
    ), env_context
    assert (
        env_setup_payload["worker_bridge_outcome"][
            "environment_setup_failure_context"
        ]["next_probe"]
        == "environment_setup_readiness_preflight_before_repeat"
    ), env_setup_payload
    assert (
        env_setup_payload["trials"][0]["environment_setup_failure_context"][
            "failure_kind"
        ]
        == "environment_setup_runtime_error_before_worker"
    ), env_setup_payload
    env_setup_compact = compact_benchmark_run(env_setup_payload)
    env_setup_health = worker_bridge_ingest_health_note(env_setup_compact)
    assert (
        env_setup_compact["worker_bridge_materialization_status"]
        == "environment_setup_failed_before_worker"
    ), env_setup_compact
    assert (
        env_setup_compact["environment_setup_failure_before_worker_count"] == 1
    ), env_setup_compact
    assert (
        env_setup_compact["environment_setup_failure_context"]["failure_kind"]
        == "environment_setup_runtime_error_before_worker"
    ), env_setup_compact
    assert (
        env_setup_compact["worker_bridge_outcome"][
            "environment_setup_failure_context"
        ]["diagnostic_granularity"]
        == "phase_fields_only_no_raw_logs"
    ), env_setup_compact
    assert (
        env_setup_compact["trials"][0]["environment_setup_failure_context"][
            "environment_setup_duration_tier"
        ]
        == "three_to_ten_minutes"
    ), env_setup_compact
    assert (
        env_setup_health["health_state"] == "environment_setup_failed_before_worker"
    ), env_setup_health
    assert (
        env_setup_health["next_action"]
        == "diagnose benchmark environment setup before worker startup"
    ), env_setup_health
    assert (
        env_setup_health["environment_setup_failure_context"]["next_probe"]
        == "environment_setup_readiness_preflight_before_repeat"
    ), env_setup_health
    assert_public_safe(env_setup_payload)
    assert_public_safe(env_setup_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-env-probe-") as tmp:
        env_probe_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_environment_setup_probe_materialized_fixture(Path(tmp))
        )
    assert env_probe_payload["environment_setup_probe_run"] is True, env_probe_payload
    assert env_probe_payload["environment_setup_probe_status"] == "materialized", (
        env_probe_payload
    )
    assert env_probe_payload["environment_setup_probe_cleared"] is True, (
        env_probe_payload
    )
    assert env_probe_payload["environment_setup_failure_before_worker_count"] == 0, (
        env_probe_payload
    )
    assert (
        "environment_setup_failed_before_worker"
        not in env_probe_payload["failure_attribution_labels"]
    ), env_probe_payload
    assert (
        "official_verifier_solution_failure"
        not in env_probe_payload["failure_attribution_labels"]
    ), env_probe_payload
    assert env_probe_payload["score_failure_attribution"] == (
        "not_applicable_environment_setup_probe"
    ), env_probe_payload
    assert env_probe_payload["trials"][0]["worker_start_status"] == (
        "environment_setup_probe_materialized"
    ), env_probe_payload
    env_probe_compact = compact_benchmark_run(env_probe_payload)
    assert env_probe_compact["environment_setup_probe_cleared"] is True, (
        env_probe_compact
    )
    assert env_probe_compact["environment_setup_failure_before_worker_count"] == 0, (
        env_probe_compact
    )
    assert_public_safe(env_probe_payload)
    assert_public_safe(env_probe_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-cli-ingest-") as tmp:
        cli_payload = run_cli_harbor_ingest_dry_run(Path(tmp))
    assert cli_payload["ok"] is True, cli_payload
    assert cli_payload["dry_run"] is True, cli_payload
    assert cli_payload["appended"] is False, cli_payload
    assert cli_payload["benchmark_run"]["mode"] == "codex_loopx", cli_payload
    assert cli_payload["benchmark_cli"]["mode"] == "codex_loopx", cli_payload
    assert (
        cli_payload["benchmark_cli"]["requested_mode"]
        == "loopx-managed-codex"
    ), cli_payload
    assert cli_payload["benchmark_cli"]["mode_source"] == "harbor_job_result", cli_payload
    assert cli_payload["benchmark_cli"]["harbor_job_result_ingested"] is True, cli_payload
    assert_public_safe(cli_payload["benchmark_run"])
    assert_public_safe(cli_payload["benchmark_cli"])
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-bare-codex-") as tmp:
        bare_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_bare_codex_fixture(Path(tmp))
        )
    assert bare_payload["mode"] == "bare_codex_cli", bare_payload
    assert bare_payload["worker_mode"] == "codex", bare_payload
    assert bare_payload["loopx_inside_case"] is False, bare_payload
    assert bare_payload["case_semantics_changed_by_harness"] is False, bare_payload
    assert bare_payload["official_score_comparable_to_native_codex"] is True, bare_payload
    assert bare_payload["worker_loopx_cli_call_total"] == 0, bare_payload
    assert bare_payload["validation"]["worker_counter_trace_loaded"] is True, bare_payload
    assert bare_payload["validation"]["worker_benchmark_run_file_present"] is True, bare_payload
    assert bare_payload["worker_bridge_outcome"]["bridge_surface"] == (
        "not_applicable_native_codex_baseline"
    ), bare_payload
    assert (
        bare_payload["overhead_attribution_counters"]["attribution_granularity"]
        == "runner_usage_and_wall_time_only"
    ), bare_payload
    assert (
        bare_payload["overhead_attribution_counters"]["loopx_cli_call_total"]
        == 0
    ), bare_payload
    bare_compact = compact_benchmark_run(bare_payload)
    assert bare_compact["validation"]["all_passed"] is True, bare_compact
    assert bare_compact["validation"]["failed_checks"] == [], bare_compact
    assert bare_compact["mode"] == "bare_codex_cli", bare_compact
    assert (
        bare_compact["overhead_attribution_counters"]["attribution_granularity"]
        == "runner_usage_and_wall_time_only"
    ), bare_compact
    assert_public_safe(bare_payload)
    assert_public_safe(bare_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-clean-zero-") as tmp:
        clean_zero_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_clean_official_zero_fixture(Path(tmp))
        )
    assert clean_zero_payload["official_task_score"]["value"] == 0.0, clean_zero_payload
    assert (
        clean_zero_payload["score_failure_attribution"]
        == "official_verifier_solution_failure"
    ), clean_zero_payload
    assert clean_zero_payload["official_zero_observation_count"] == 1, clean_zero_payload
    zero_observation = clean_zero_payload["trials"][0]["official_zero_observation"]
    assert zero_observation["detected"] is True, zero_observation
    assert zero_observation["agent_setup_completed"] is True, zero_observation
    assert zero_observation["agent_execution_completed"] is True, zero_observation
    assert zero_observation["verifier_completed"] is True, zero_observation
    assert zero_observation["raw_logs_read"] is False, zero_observation
    clean_zero_compact = compact_benchmark_run(clean_zero_payload)
    assert clean_zero_compact["official_zero_observation_count"] == 1, clean_zero_compact
    assert (
        clean_zero_compact["score_failure_attribution"]
        == "official_verifier_solution_failure"
    ), clean_zero_compact
    compact_zero_observation = clean_zero_compact["trials"][0][
        "official_zero_observation"
    ]
    assert compact_zero_observation["detected"] is True, compact_zero_observation
    assert (
        compact_zero_observation["task_text_read"] is False
    ), compact_zero_observation
    assert_public_safe(clean_zero_payload)
    assert_public_safe(clean_zero_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-goal-mode-baseline-") as tmp:
        goal_mode_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_codex_goal_mode_baseline_fixture(Path(tmp))
        )
    assert goal_mode_payload["mode"] == "codex_goal_mode_baseline", goal_mode_payload
    assert goal_mode_payload["worker_mode"] == "codex_goal_mode_baseline", goal_mode_payload
    assert goal_mode_payload["codex_goal_mode_baseline"] is True, goal_mode_payload
    assert goal_mode_payload["loopx_inside_case"] is False, goal_mode_payload
    assert goal_mode_payload["case_semantics_changed_by_harness"] is False, goal_mode_payload
    assert goal_mode_payload["model_plus_harness_pair"] is False, goal_mode_payload
    assert goal_mode_payload["control_plane_score_applicable"] is False, goal_mode_payload
    assert (
        goal_mode_payload["official_score_comparable_to_loopx_treatment"]
        is True
    ), goal_mode_payload
    assert goal_mode_payload["interaction_counters"] is None, goal_mode_payload
    assert goal_mode_payload["validation"]["raw_trajectory_excluded"] is True, goal_mode_payload
    assert "trial:agent/trajectory.json" not in goal_mode_payload["evidence_files"], goal_mode_payload
    assert (
        goal_mode_payload["worker_bridge_outcome"]["bridge_surface"]
        == TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE
    ), goal_mode_payload
    goal_mode_compact = compact_benchmark_run(goal_mode_payload)
    assert goal_mode_compact["mode"] == "codex_goal_mode_baseline", goal_mode_compact
    assert goal_mode_compact["worker_mode"] == "codex_goal_mode_baseline", goal_mode_compact
    assert goal_mode_compact["loopx_inside_case"] is False, goal_mode_compact
    assert (
        goal_mode_compact["case_semantics_changed_by_harness"] is False
    ), goal_mode_compact
    assert goal_mode_compact.get("interaction_counters") is None, goal_mode_compact
    assert (
        goal_mode_compact["worker_bridge_outcome"]["bridge_surface"]
        == TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE
    ), goal_mode_compact
    assert_public_safe(goal_mode_payload)
    assert_public_safe(goal_mode_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-no-packet-runtime-") as tmp:
        no_packet_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_no_packet_runtime_goal_fixture(Path(tmp))
        )
    assert no_packet_payload["mode"] == "codex_loopx_no_packet", no_packet_payload
    assert no_packet_payload["worker_loopx_cli_call_total"] == 0, no_packet_payload
    assert no_packet_payload["worker_counter_trace_trial_count"] == 0, no_packet_payload
    assert no_packet_payload["worker_bridge_outcome"]["counter_trace_present"] is False, no_packet_payload
    assert no_packet_payload["interaction_counters"] is None, no_packet_payload
    assert no_packet_payload["validation"]["raw_trajectory_excluded"] is True, no_packet_payload
    assert "trial:agent/trajectory.json" not in no_packet_payload["evidence_files"], no_packet_payload
    assert (
        no_packet_payload["overhead_attribution_counters"][
            "attribution_granularity"
        ]
        == "runner_usage_and_wall_time_only"
    ), no_packet_payload
    assert (
        no_packet_payload["overhead_attribution_counters"][
            "codex_runtime_goal_tool_call_total"
        ]
        == 0
    ), no_packet_payload
    no_packet_compact = compact_benchmark_run(no_packet_payload)
    assert no_packet_compact.get("interaction_counters") is None, no_packet_compact
    assert (
        no_packet_compact["overhead_attribution_counters"][
            "attribution_granularity"
        ]
        == "runner_usage_and_wall_time_only"
    ), no_packet_compact
    assert_public_safe(no_packet_payload)
    assert_public_safe(no_packet_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-private-trajectory-counts-") as tmp:
        no_packet_private_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_no_packet_runtime_goal_fixture(Path(tmp)),
            trace_publicness="private_debug_counts_from_raw_trajectory",
            include_codex_trajectory_counts=True,
        )
    private_counters = no_packet_private_payload["interaction_counters"]
    assert private_counters["loopx_cli_calls"]["total"] == 0, private_counters
    assert private_counters["codex_runtime_goal_tool_calls"]["create_goal"] == 1, private_counters
    assert private_counters["codex_runtime_goal_tool_calls"]["update_goal"] == 1, private_counters
    assert private_counters["codex_runtime_goal_tool_calls"]["total"] == 2, private_counters
    assert private_counters["codex_runtime_goal_tool_trial_count"] == 1, private_counters
    assert (
        private_counters["counter_trust_level"]
        == "runner_loaded_codex_trajectory_no_worker_trace"
    ), private_counters
    assert (
        private_counters["case_result_writeback"]
        == "runner_side_guaranteed_writeback_no_worker_cli_bridge"
    ), private_counters
    assert no_packet_private_payload["validation"]["raw_trajectory_excluded"] is False, no_packet_private_payload
    assert "trial:agent/trajectory.json" in no_packet_private_payload["evidence_files"], no_packet_private_payload
    assert (
        no_packet_private_payload["overhead_attribution_counters"][
            "attribution_granularity"
        ]
        == "codex_runtime_goal_tool_counts_only"
    ), no_packet_private_payload
    assert (
        no_packet_private_payload["overhead_attribution_counters"][
            "codex_runtime_goal_tool_call_total"
        ]
        == 2
    ), no_packet_private_payload
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-partial-stats-") as tmp:
        partial_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_partial_harbor_stats_fixture(Path(tmp))
        )
    assert partial_payload["official_task_score"]["value"] == 2 / 3, partial_payload
    assert partial_payload["official_task_score"]["source"] == "harbor_stats_eval_mean", partial_payload
    assert partial_payload["official_task_score"]["passed"] is False, partial_payload
    assert partial_payload["progress"]["n_errored_trials"] == 1, partial_payload
    assert partial_payload["worker_bridge_outcome"]["official_score_value"] == 2 / 3, partial_payload
    partial_compact = compact_benchmark_run(partial_payload)
    assert partial_compact["official_task_score"]["value"] == 2 / 3, partial_compact
    assert partial_compact["official_task_score"]["passed"] is False, partial_compact
    assert_public_safe(partial_payload)
    assert_public_safe(partial_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-runner-ingest-long-") as tmp:
        long_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_fixture(Path(tmp), agent_timeout_multiplier=2.0)
        )
    long_policy = long_payload["worker_bridge_outcome"]["wall_time_policy"]
    assert (
        long_policy["timeout_tier"] == "private_extended_timeout_agent_multiplier"
    ), long_policy
    assert long_policy["changes_official_benchmark_timeout"] is True, long_policy
    assert long_policy["official_timeout_comparable"] is False, long_policy
    assert long_policy["wall_time_limit_seconds"] == 1800.0, long_policy
    assert long_policy["observed_true_long_task_bar_met"] is False, long_policy
    assert long_policy["expected_true_long_task_bar_met"] is True, long_policy
    assert long_policy["true_long_task_bar_met"] is True, long_policy
    assert long_policy["expected_hours_scale_bar_met"] is False, long_policy
    long_compact = compact_benchmark_run(long_payload)
    assert (
        long_compact["worker_bridge_outcome"]["wall_time_policy"]["timeout_tier"]
        == "private_extended_timeout_agent_multiplier"
    ), long_compact
    assert (
        long_compact["worker_bridge_outcome"]["wall_time_policy"][
            "changes_official_benchmark_timeout"
        ]
        is True
    ), long_compact
    assert (
        long_compact["worker_bridge_outcome"]["wall_time_policy"][
            "expected_true_long_task_bar_met"
        ]
        is True
    ), long_compact
    assert (
        long_compact["worker_bridge_outcome"]["wall_time_policy"][
            "true_long_task_bar_met"
        ]
        is True
    ), long_compact
    assert_public_safe(long_payload)
    assert_public_safe(long_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-verifier-failure-default-") as tmp:
        failure_default_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_verifier_dependency_failure_fixture(Path(tmp))
        )
    assert failure_default_payload["official_task_score"]["value"] == 0.0, failure_default_payload
    assert failure_default_payload["score_failure_attribution"] == "none", failure_default_payload
    assert failure_default_payload["verifier_dependency_failure_count"] == 0, failure_default_payload
    assert failure_default_payload["failure_attribution_labels"] == [], failure_default_payload
    assert failure_default_payload["validation"]["verifier_logs_excluded"] is True, failure_default_payload
    assert_public_safe(failure_default_payload)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-worker-self-mismatch-") as tmp:
        mismatch_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_worker_self_validation_mismatch_fixture(Path(tmp))
        )
    assert mismatch_payload["official_task_score"]["value"] == 0.0, mismatch_payload
    assert mismatch_payload["worker_bridge_materialization_status"] == "verified", mismatch_payload
    assert (
        mismatch_payload["worker_self_validation_official_score_mismatch_count"]
        == 1
    ), mismatch_payload
    assert (
        mismatch_payload["score_failure_attribution"]
        == "worker_self_validation_official_score_mismatch"
    ), mismatch_payload
    assert "worker_self_validation_official_score_mismatch" in mismatch_payload[
        "failure_attribution_labels"
    ], mismatch_payload
    assert (
        mismatch_payload["worker_bridge_outcome"][
            "worker_self_validation_official_score_mismatch_count"
        ]
        == 1
    ), mismatch_payload
    mismatch_compact = compact_benchmark_run(mismatch_payload)
    assert (
        mismatch_compact["score_failure_attribution"]
        == "worker_self_validation_official_score_mismatch"
    ), mismatch_compact
    assert (
        mismatch_compact["worker_self_validation_official_score_mismatch_count"]
        == 1
    ), mismatch_compact
    assert_public_safe(mismatch_payload)
    assert_public_safe(mismatch_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-worker-scope-ambiguous-") as tmp:
        ambiguous_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_worker_validation_scope_ambiguous_fixture(Path(tmp))
        )
    assert ambiguous_payload["official_task_score"]["value"] == 0.0, ambiguous_payload
    assert (
        ambiguous_payload["worker_self_validation_official_score_mismatch_count"]
        == 0
    ), ambiguous_payload
    assert (
        ambiguous_payload[
            "worker_validation_scope_ambiguous_official_score_failure_count"
        ]
        == 1
    ), ambiguous_payload
    assert (
        ambiguous_payload["score_failure_attribution"]
        == "worker_validation_scope_ambiguous_official_score_failure"
    ), ambiguous_payload
    ambiguous_compact = compact_benchmark_run(ambiguous_payload)
    assert (
        ambiguous_compact["score_failure_attribution"]
        == "worker_validation_scope_ambiguous_official_score_failure"
    ), ambiguous_compact
    assert (
        ambiguous_compact[
            "worker_validation_scope_ambiguous_official_score_failure_count"
        ]
        == 1
    ), ambiguous_compact
    assert_public_safe(ambiguous_payload)
    assert_public_safe(ambiguous_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-verifier-failure-") as tmp:
        failure_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_verifier_dependency_failure_fixture(Path(tmp)),
            include_verifier_log_attribution=True,
        )
    assert failure_payload["official_task_score"]["value"] == 0.0, failure_payload
    assert failure_payload["official_task_score"]["passed"] is False, failure_payload
    assert (
        failure_payload["score_failure_attribution"]
        == "verifier_dependency_install_failure"
    ), failure_payload
    assert failure_payload["verifier_dependency_failure_count"] == 1, failure_payload
    assert "verifier_dependency_install_failure" in failure_payload[
        "failure_attribution_labels"
    ], failure_payload
    failure_trial = failure_payload["trials"][0]
    assert (
        failure_trial["verifier_failure_attribution"]
        == "verifier_dependency_install_failure"
    ), failure_trial
    assert (
        "verifier_uv_install_or_download_failure"
        in failure_trial["verifier_failure_attribution_labels"]
    ), failure_trial
    assert (
        failure_payload["worker_bridge_outcome"]["score_failure_attribution"]
        == "verifier_dependency_install_failure"
    ), failure_payload
    failure_compact = compact_benchmark_run(failure_payload)
    assert (
        failure_compact["score_failure_attribution"]
        == "verifier_dependency_install_failure"
    ), failure_compact
    assert failure_compact["verifier_dependency_failure_count"] == 1, failure_compact
    assert "verifier_dependency_install_failure" in failure_compact[
        "failure_attribution_labels"
    ], failure_compact
    assert (
        failure_compact["trials"][0]["verifier_failure_attribution"]
        == "verifier_dependency_install_failure"
    ), failure_compact
    assert failure_payload["validation"]["verifier_logs_excluded"] is False, failure_payload
    assert failure_compact["validation"]["failed_checks"] == ["verifier_logs_excluded"], failure_compact
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-platform-failure-") as tmp:
        platform_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_verifier_platform_probe_failure_fixture(Path(tmp)),
            include_verifier_log_attribution=True,
        )
    assert platform_payload["official_task_score"]["value"] == 0.0, platform_payload
    assert platform_payload["official_task_score"]["passed"] is False, platform_payload
    assert (
        platform_payload["score_failure_attribution"]
        == "verifier_platform_probe_failure"
    ), platform_payload
    assert platform_payload["verifier_dependency_failure_count"] == 0, platform_payload
    assert platform_payload["verifier_failure_attribution_count"] == 1, platform_payload
    assert platform_payload["submit_eligible"] is False, platform_payload
    assert platform_payload["worker_submit_eligible_mismatch_count"] == 1, platform_payload
    assert (
        platform_payload["worker_submit_eligible_mismatch_reason"]
        == "worker_file_submit_eligible_true_under_runner_no_upload_boundary"
    ), platform_payload
    assert (
        platform_payload["validation"]["worker_submit_eligible_matches_runner_boundary"]
        is False
    ), platform_payload
    assert (
        platform_payload["interaction_counters"]["worker_submit_eligible_mismatch_count"]
        == 1
    ), platform_payload
    assert (
        platform_payload["overhead_attribution_counters"][
            "worker_submit_eligible_mismatch_count"
        ]
        == 1
    ), platform_payload
    assert (
        platform_payload["worker_bridge_outcome"][
            "worker_submit_eligible_mismatch_observed"
        ]
        is True
    ), platform_payload
    assert "verifier_platform_probe_failure" in platform_payload[
        "failure_attribution_labels"
    ], platform_payload
    platform_trial = platform_payload["trials"][0]
    assert (
        platform_trial["verifier_failure_attribution"]
        == "verifier_infrastructure_failure"
    ), platform_trial
    assert (
        "verifier_platform_probe_failure"
        in platform_trial["verifier_failure_attribution_labels"]
    ), platform_trial
    assert (
        platform_payload["worker_bridge_outcome"]["score_failure_attribution"]
        == "verifier_platform_probe_failure"
    ), platform_payload
    platform_compact = compact_benchmark_run(platform_payload)
    assert (
        platform_compact["score_failure_attribution"]
        == "verifier_platform_probe_failure"
    ), platform_compact
    assert platform_compact["verifier_dependency_failure_count"] == 0, platform_compact
    assert platform_compact["verifier_failure_attribution_count"] == 1, platform_compact
    assert platform_compact["worker_submit_eligible_mismatch_count"] == 1, platform_compact
    assert (
        platform_compact["worker_submit_eligible_mismatch_reason"]
        == "worker_file_submit_eligible_true_under_runner_no_upload_boundary"
    ), platform_compact
    assert "worker_submit_eligible_matches_runner_boundary" in platform_compact[
        "validation"
    ]["failed_checks"], platform_compact
    assert "verifier_logs_excluded" in platform_compact["validation"]["failed_checks"], platform_compact
    assert (
        platform_compact["worker_bridge_outcome"][
            "worker_submit_eligible_mismatch_observed"
        ]
        is True
    ), platform_compact
    assert "verifier_platform_probe_failure" in platform_compact[
        "failure_attribution_labels"
    ], platform_compact
    assert (
        platform_compact["trials"][0]["verifier_failure_attribution"]
        == "verifier_infrastructure_failure"
    ), platform_compact
    assert_public_safe(platform_payload)
    assert_public_safe(platform_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-timeout-attribution-") as tmp:
        timeout_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_worker_trace_timeout_writeback_loss_fixture(Path(tmp)),
        )
    assert timeout_payload["official_task_score"]["value"] == 0.0, timeout_payload
    assert (
        timeout_payload["score_failure_attribution"]
        == "agent_timeout_before_solution_completion"
    ), timeout_payload
    assert "agent_timeout_before_solution_completion" in timeout_payload[
        "failure_attribution_labels"
    ], timeout_payload
    assert (
        timeout_payload["worker_bridge_outcome"]["score_failure_attribution"]
        == "agent_timeout_before_solution_completion"
    ), timeout_payload
    timeout_compact = compact_benchmark_run(timeout_payload)
    assert (
        timeout_compact["score_failure_attribution"]
        == "agent_timeout_before_solution_completion"
    ), timeout_compact
    assert "agent_timeout_before_solution_completion" in timeout_compact[
        "failure_attribution_labels"
    ], timeout_compact
    assert_public_safe(timeout_payload)
    assert_public_safe(timeout_compact)
    with tempfile.TemporaryDirectory(prefix="loopx-harbor-timeout-writeback-loss-") as tmp:
        writeback_loss_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_worker_trace_timeout_writeback_loss_fixture(Path(tmp)),
            include_verifier_log_attribution=True,
        )
    assert writeback_loss_payload["official_task_score"]["value"] == 0.0, writeback_loss_payload
    assert (
        writeback_loss_payload["score_failure_attribution"]
        == "verifier_platform_probe_failure"
    ), writeback_loss_payload
    assert writeback_loss_payload["worker_counter_trace_trial_count"] == 1, writeback_loss_payload
    assert writeback_loss_payload["worker_benchmark_run_file_count"] == 0, writeback_loss_payload
    assert writeback_loss_payload["worker_benchmark_run_schema_ok_count"] == 0, writeback_loss_payload
    assert writeback_loss_payload["worker_bridge_writeback_loss_count"] == 1, writeback_loss_payload
    assert (
        writeback_loss_payload["worker_bridge_writeback_loss_reason"]
        == "agent_timeout_after_worker_trace_before_benchmark_run_writeback"
    ), writeback_loss_payload
    writeback_loss_counters = writeback_loss_payload["interaction_counters"]
    assert writeback_loss_counters["loopx_cli_calls"]["active_user_observe"] == 1, writeback_loss_counters
    assert writeback_loss_counters["loopx_cli_calls"]["check"] == 1, writeback_loss_counters
    assert writeback_loss_counters["worker_bridge_writeback_loss_count"] == 1, writeback_loss_counters
    assert (
        writeback_loss_counters["worker_bridge_writeback_loss_reason"]
        == "agent_timeout_after_worker_trace_before_benchmark_run_writeback"
    ), writeback_loss_counters
    writeback_loss_outcome = writeback_loss_payload["worker_bridge_outcome"]
    assert (
        writeback_loss_outcome["runner_return_status"]
        == "completed_with_agent_timeout"
    ), writeback_loss_outcome
    assert writeback_loss_outcome["worker_bridge_verified"] is True, writeback_loss_outcome
    assert writeback_loss_outcome["worker_bridge_writeback_loss_observed"] is True, writeback_loss_outcome
    assert writeback_loss_outcome["worker_bridge_writeback_loss_count"] == 1, writeback_loss_outcome
    assert (
        writeback_loss_outcome["worker_bridge_writeback_loss_reason"]
        == "agent_timeout_after_worker_trace_before_benchmark_run_writeback"
    ), writeback_loss_outcome
    writeback_loss_validation = writeback_loss_payload["validation"]
    assert (
        writeback_loss_validation["worker_benchmark_run_file_present"] is False
    ), writeback_loss_validation
    assert (
        writeback_loss_validation["worker_benchmark_run_schema_ok"] is False
    ), writeback_loss_validation
    assert (
        writeback_loss_validation["worker_benchmark_run_present_for_traced_trials"]
        is False
    ), writeback_loss_validation
    writeback_loss_compact = compact_benchmark_run(writeback_loss_payload)
    assert writeback_loss_compact["validation"]["all_passed"] is False, writeback_loss_compact
    assert "worker_benchmark_run_file_present" in writeback_loss_compact[
        "validation"
    ]["failed_checks"], writeback_loss_compact
    assert writeback_loss_compact["worker_bridge_writeback_loss_count"] == 1, writeback_loss_compact
    assert (
        writeback_loss_compact["worker_bridge_writeback_loss_reason"]
        == "agent_timeout_after_worker_trace_before_benchmark_run_writeback"
    ), writeback_loss_compact
    assert (
        writeback_loss_compact["overhead_attribution_counters"][
            "worker_bridge_writeback_loss_count"
        ]
        == 1
    ), writeback_loss_compact
    assert (
        writeback_loss_compact["worker_bridge_outcome"][
            "worker_bridge_writeback_loss_observed"
        ]
        is True
    ), writeback_loss_compact
    assert (
        writeback_loss_compact["worker_bridge_outcome"][
            "worker_bridge_writeback_loss_count"
        ]
        == 1
    ), writeback_loss_compact
    assert_public_safe(writeback_loss_payload)
    assert_public_safe(writeback_loss_compact)
    print("terminal-bench-harbor-runner-ingest-smoke ok")


if __name__ == "__main__":
    main()
