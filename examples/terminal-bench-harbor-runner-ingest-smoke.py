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

from goal_harness.benchmark import (  # noqa: E402
    _iso_duration_seconds,
    build_terminal_bench_harbor_result_benchmark_run,
)
from goal_harness.status import compact_benchmark_run  # noqa: E402

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
    job_dir = root / f"terminal_bench_sample_build_cython_ext_codex_goal_harness_active_e2e_{suffix}"
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
        "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex",
        "--model",
        "gpt-5.5",
        "--agent-env",
        "CODEX_FORCE_AUTH_JSON=****",
        "--agent-kwarg",
        "goal_harness_mode=codex_goal_harness",
        "--agent-kwarg",
        "goal_harness_cli_bridge_enabled=true",
    ]
    agent = {
        "import_path": "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "goal_harness_mode": "codex_goal_harness",
            "goal_harness_cli_bridge_enabled": True,
            "goal_harness_goal_id": "goal-harness-meta",
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
    write_json(trial_dir / "agent" / "goal-harness-worker-benchmark-run.json", {"schema_version": "benchmark_run_v0"})
    trace_rows = [
        {"command": "status", "ok": True},
        {"command": "quota_should_run", "ok": True},
        {"command": "history", "ok": True},
        {"command": "check", "ok": True},
        {"command": "append_benchmark_run", "ok": False, "error_kind": "schema_rejected"},
        {"command": "append_benchmark_run", "ok": True, "dry_run": True},
    ]
    (trial_dir / "agent" / "goal-harness-counter-trace.jsonl").write_text(
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


def write_cli_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"

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
                    "domain": "goal-harness-platform",
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
            "goal_harness.cli",
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
        "import_path": "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "goal_harness_mode": "codex_goal_harness",
            "goal_harness_cli_bridge_enabled": True,
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
        trial_dir / "agent" / "goal-harness-worker-benchmark-run.json",
        {"schema_version": "benchmark_run_v0"},
    )
    (trial_dir / "agent" / "goal-harness-counter-trace.jsonl").write_text(
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


def write_no_packet_runtime_goal_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_no_packet_runtime_goal_tools"
    trial_dir = job_dir / "build-cython-ext__nopacket"
    agent = {
        "import_path": "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "goal_harness_mode": "codex_goal_harness",
            "goal_harness_access_packet_mode": "none",
            "goal_harness_goal_id": "goal-harness-meta",
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
                "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex",
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


def write_partial_harbor_stats_fixture(root: Path) -> Path:
    job_dir = root / "terminal_bench_sample_partial_harbor_stats"
    agent = {
        "import_path": "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex",
        "model_name": "gpt-5.5",
        "kwargs": {
            "goal_harness_mode": "codex_goal_harness",
            "goal_harness_cli_bridge_enabled": True,
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
                "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex",
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
                    "goal-harness-managed-codex__gpt-5.5__sample": {
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
            trial_dir / "agent" / "goal-harness-worker-benchmark-run.json",
            {"schema_version": "benchmark_run_v0"},
        )
        if reward is not None:
            (trial_dir / "agent" / "goal-harness-counter-trace.jsonl").write_text(
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

    with tempfile.TemporaryDirectory(prefix="goal-harness-harbor-runner-ingest-") as tmp:
        payload = build_terminal_bench_harbor_result_benchmark_run(write_fixture(Path(tmp)))

    assert payload["schema_version"] == "benchmark_run_v0", payload
    assert payload["source_runner"] == "harbor", payload
    assert payload["benchmark_id"] == "terminal-bench-sample@2.0", payload
    assert payload["mode"] == "codex_goal_harness", payload
    assert payload["goal_harness_inside_case"] is True, payload
    assert payload["worker_goal_harness_cli_call_total"] == 6, payload
    assert payload["worker_counter_trace_trial_count"] == 1, payload
    assert payload["worker_benchmark_run_file_count"] == 1, payload
    assert payload["worker_benchmark_run_schema_ok_count"] == 1, payload
    assert payload["pre_worker_agent_setup_failure_count"] == 1, payload
    assert payload["interaction_counters"]["goal_harness_cli_calls"]["append_benchmark_run"] == 2, payload
    assert payload["interaction_counters"]["append_benchmark_run_success_count"] == 1, payload
    assert payload["interaction_counters"]["append_benchmark_run_schema_rejected_count"] == 1, payload
    assert payload["interaction_counters"]["worker_counter_trace_trial_count"] == 1, payload
    assert payload["interaction_counters"]["worker_benchmark_run_file_count"] == 1, payload
    assert payload["interaction_counters"]["worker_benchmark_run_schema_ok_count"] == 1, payload
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
    assert overhead["goal_harness_cli_call_total"] == 6, overhead
    assert overhead["goal_harness_required_cli_call_total"] == 3, overhead
    assert overhead["goal_harness_optional_context_cli_call_total"] == 3, overhead
    assert overhead["append_benchmark_run_success_count"] == 1, overhead
    assert payload["official_task_score"]["value"] == 1.0, payload
    assert payload["progress"]["n_errored_trials"] == 2, payload
    assert payload["trials"][0]["exception_type"] == "AgentTimeoutError", payload
    passed_trial = next(trial for trial in payload["trials"] if trial["task_id"] == "build-cython-ext")
    assert "verifier_failure_attribution" not in passed_trial, passed_trial
    assert payload["verifier_dependency_failure_count"] == 0, payload
    setup_trial = next(
        trial for trial in payload["trials"] if trial["task_id"] == "fix-code-vulnerability"
    )
    assert setup_trial["worker_start_status"] == "pre_worker_agent_setup_failed", setup_trial
    assert payload["worker_bridge_outcome"]["runner_return_status"] == "completed_with_agent_timeout", payload
    assert payload["worker_bridge_outcome"]["pre_worker_agent_setup_failure_count"] == 1, payload
    episode_policy = payload["episode_policy"]
    assert (
        episode_policy["mode"] == "single_codex_agent_goal_harness_assisted_checkpoints"
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
    compact = compact_benchmark_run(payload)
    assert compact and compact["worker_goal_harness_cli_call_total"] == 6, compact
    assert compact["worker_counter_trace_trial_count"] == 1, compact
    assert compact["worker_benchmark_run_file_count"] == 1, compact
    assert compact["worker_benchmark_run_schema_ok_count"] == 1, compact
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
    assert compact_overhead["goal_harness_cli_call_total"] == 6, compact_overhead
    assert compact_overhead["worker_bridge_event_count"] == 6, compact_overhead
    assert compact["trials"][0]["exception_type"] == "AgentTimeoutError", compact
    compact_setup_trial = next(
        trial for trial in compact["trials"] if trial["task_id"] == "fix-code-vulnerability"
    )
    assert compact_setup_trial["worker_start_status"] == "pre_worker_agent_setup_failed", compact
    assert compact["official_task_score"]["passed"] is True, compact
    assert (
        compact["episode_policy"]["mode"]
        == "single_codex_agent_goal_harness_assisted_checkpoints"
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
    assert_public_safe(payload)
    assert_public_safe(compact)
    with tempfile.TemporaryDirectory(prefix="goal-harness-harbor-cli-ingest-") as tmp:
        cli_payload = run_cli_harbor_ingest_dry_run(Path(tmp))
    assert cli_payload["ok"] is True, cli_payload
    assert cli_payload["dry_run"] is True, cli_payload
    assert cli_payload["appended"] is False, cli_payload
    assert cli_payload["benchmark_run"]["mode"] == "codex_goal_harness", cli_payload
    assert cli_payload["benchmark_cli"]["mode"] == "codex_goal_harness", cli_payload
    assert (
        cli_payload["benchmark_cli"]["requested_mode"]
        == "goal-harness-managed-codex"
    ), cli_payload
    assert cli_payload["benchmark_cli"]["mode_source"] == "harbor_job_result", cli_payload
    assert cli_payload["benchmark_cli"]["harbor_job_result_ingested"] is True, cli_payload
    assert_public_safe(cli_payload["benchmark_run"])
    assert_public_safe(cli_payload["benchmark_cli"])
    with tempfile.TemporaryDirectory(prefix="goal-harness-harbor-bare-codex-") as tmp:
        bare_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_bare_codex_fixture(Path(tmp))
        )
    assert bare_payload["mode"] == "bare_codex_cli", bare_payload
    assert bare_payload["worker_mode"] == "codex", bare_payload
    assert bare_payload["goal_harness_inside_case"] is False, bare_payload
    assert bare_payload["case_semantics_changed_by_harness"] is False, bare_payload
    assert bare_payload["official_score_comparable_to_native_codex"] is True, bare_payload
    assert bare_payload["worker_goal_harness_cli_call_total"] == 0, bare_payload
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
        bare_payload["overhead_attribution_counters"]["goal_harness_cli_call_total"]
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
    with tempfile.TemporaryDirectory(prefix="goal-harness-harbor-no-packet-runtime-") as tmp:
        no_packet_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_no_packet_runtime_goal_fixture(Path(tmp))
        )
    assert no_packet_payload["mode"] == "codex_goal_harness_no_packet", no_packet_payload
    assert no_packet_payload["worker_goal_harness_cli_call_total"] == 0, no_packet_payload
    assert no_packet_payload["worker_counter_trace_trial_count"] == 0, no_packet_payload
    assert no_packet_payload["worker_bridge_outcome"]["counter_trace_present"] is False, no_packet_payload
    counters = no_packet_payload["interaction_counters"]
    assert counters["goal_harness_cli_calls"]["total"] == 0, counters
    assert counters["codex_runtime_goal_tool_calls"]["create_goal"] == 1, counters
    assert counters["codex_runtime_goal_tool_calls"]["update_goal"] == 1, counters
    assert counters["codex_runtime_goal_tool_calls"]["total"] == 2, counters
    assert counters["codex_runtime_goal_tool_trial_count"] == 1, counters
    assert (
        counters["counter_trust_level"]
        == "runner_loaded_codex_trajectory_no_worker_trace"
    ), counters
    assert (
        counters["case_result_writeback"]
        == "runner_side_guaranteed_writeback_no_worker_cli_bridge"
    ), counters
    assert (
        no_packet_payload["overhead_attribution_counters"][
            "attribution_granularity"
        ]
        == "codex_runtime_goal_tool_counts_only"
    ), no_packet_payload
    assert (
        no_packet_payload["overhead_attribution_counters"][
            "codex_runtime_goal_tool_call_total"
        ]
        == 2
    ), no_packet_payload
    no_packet_compact = compact_benchmark_run(no_packet_payload)
    assert no_packet_compact["interaction_counters"]["goal_harness_cli_calls"]["total"] == 0, no_packet_compact
    assert (
        no_packet_compact["interaction_counters"]["codex_runtime_goal_tool_calls"]["total"]
        == 2
    ), no_packet_compact
    assert (
        no_packet_compact["interaction_counters"]["codex_runtime_goal_tool_trial_count"]
        == 1
    ), no_packet_compact
    assert (
        no_packet_compact["overhead_attribution_counters"][
            "attribution_granularity"
        ]
        == "codex_runtime_goal_tool_counts_only"
    ), no_packet_compact
    assert_public_safe(no_packet_payload)
    assert_public_safe(no_packet_compact)
    with tempfile.TemporaryDirectory(prefix="goal-harness-harbor-partial-stats-") as tmp:
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
    with tempfile.TemporaryDirectory(prefix="goal-harness-harbor-runner-ingest-long-") as tmp:
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
    with tempfile.TemporaryDirectory(prefix="goal-harness-harbor-verifier-failure-") as tmp:
        failure_payload = build_terminal_bench_harbor_result_benchmark_run(
            write_verifier_dependency_failure_fixture(Path(tmp))
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
    assert_public_safe(failure_payload)
    assert_public_safe(failure_compact)
    print("terminal-bench-harbor-runner-ingest-smoke ok")


if __name__ == "__main__":
    main()
