#!/usr/bin/env python3
"""Smoke-test the benchmark baseline-failure gate reducer CLI."""

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

from loopx.status import collect_status  # noqa: E402


GOAL_ID = "benchmark-baseline-failure-gate-smoke"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_ID = "fix-code-vulnerability"
BASELINE_SCENARIO = "codex_goal_mode_baseline"

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "raw" + "_log",
    "session" + "_history",
    "sk-" + "example",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    baseline_result_path = root / "baseline_result.json"
    baseline_run_path = root / "baseline_run.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-06-13T00:00:00+00:00\n"
        "---\n\n"
        "# Baseline Failure Gate Smoke\n\n"
        "## Agent Todo\n\n"
        "- [ ] Reduce compact goal-mode baseline result through the baseline-failure gate.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-13T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "loopx-platform",
                    "status": "active",
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
    write_json(
        baseline_result_path,
        {
            "schema_version": "benchmark_result_v0",
            "task_id": TASK_ID,
            "scenario_id": BASELINE_SCENARIO,
            "worker_mode": "codex_goal_mode_baseline",
            "harness_identity": "codex_goal_mode",
            "worker_surface": "codex_cli_goal_mode",
            "terminal_state": "failed",
            "official_task_score": {
                "kind": "terminal_bench_verifier",
                "passed": False,
                "value": 0.0,
            },
            "failure_attribution_labels": [
                "worker_trace_without_benchmark_run_writeback",
            ],
            "trace_publicness": "compact_public",
            "raw_log_path": "/" + "tmp/private/raw.log",
        },
    )
    write_json(
        baseline_run_path,
        {
            "classification": "terminal_bench_baseline_compact_result",
            "benchmark_run": {
                "schema_version": "benchmark_run_v0",
                "benchmark_id": BENCHMARK_ID,
                "job_name": "terminal_bench_fix_code_vulnerability_codex_goal_mode_baseline",
                "mode": BASELINE_SCENARIO,
                "worker_mode": "codex_goal_mode_baseline",
                "trace_publicness": "compact_public",
                "runner_return_status": "completed",
                "official_score_status": "completed",
                "official_score": 0.0,
                "official_task_score": {
                    "kind": "terminal_bench_verifier",
                    "passed": False,
                    "value": 0.0,
                },
                "score_failure_attribution": "worker_trace_without_benchmark_run_writeback",
                "worker_bridge_outcome": {
                    "schema_version": "worker_bridge_outcome_v0",
                    "score_failure_attribution": "none",
                    "trace_publicness": "compact_public",
                    "raw_paths_recorded": False,
                    "credential_values_recorded": False,
                },
                "trials": [
                    {
                        "task_id": TASK_ID,
                        "exception_type": "none",
                        "verifier_reward_present": True,
                    }
                ],
                "raw_log_path": "/" + "tmp/private/raw.log",
            },
        },
    )
    return registry_path, runtime, baseline_result_path, baseline_run_path


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_cli_json(args: list[str]) -> dict[str, Any]:
    result = run_cli(args)
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def base_args(registry_path: Path, runtime: Path, result_path: Path) -> list[str]:
    return [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "benchmark",
        "baseline-failure-gate",
        "--benchmark-id",
        BENCHMARK_ID,
        "--baseline-result-json",
        str(result_path),
        "--baseline-mode",
        "codex_cli_goal_mode",
        "--treatment-scenario-id",
        "codex_loopx",
        "--failure-phase",
        "writeback",
        "--failure-class",
        "worker_trace_without_benchmark_run_writeback",
        "--failure-attribution-label",
        "worker_trace_without_benchmark_run_writeback",
        "--minimum-next-evidence",
        "run same-task LoopX treatment with compact writeback required",
        "--evidence-ref",
        f"benchmark_result_v0:{BASELINE_SCENARIO}",
        "--no-global-sync",
    ]


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 16000, len(text)


def assert_gate(
    payload: dict[str, Any],
    *,
    eligible: bool,
    appended: bool,
    source: str = "compact_benchmark_result_v0",
) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    comparison = payload["benchmark_comparison"]
    assert comparison["schema_version"] == "benchmark_comparison_v0", comparison
    assert comparison["benchmark_id"] == BENCHMARK_ID, comparison
    assert comparison["task_id"] == TASK_ID, comparison
    assert comparison["baseline_scenario_id"] == BASELINE_SCENARIO, comparison
    gate = comparison["baseline_failure_gate"]
    assert gate["schema_version"] == "benchmark_baseline_failure_gate_v0", gate
    assert gate["baseline_failed"] is True, gate
    assert gate["failure_phase"] == "writeback", gate
    assert gate["failure_class"] == "worker_trace_without_benchmark_run_writeback", gate
    assert gate["treatment_eligible"] is eligible, gate
    assert gate["control_plane_addressable"] is eligible, gate
    if eligible:
        assert gate["same_task_semantics"] is True, gate
        assert gate["same_runner_protocol"] is True, gate
        assert gate["trace_publicness_verified"] is True, gate
    else:
        assert gate["negative_selection_reason"], gate
    assert payload["baseline_gate_cli"]["source"] == source, payload
    assert payload["baseline_gate_cli"]["accepted_schemas"] == [
        "benchmark_result_v0",
        "benchmark_run_v0",
    ], payload
    assert_public_safe(payload)


def assert_status_projection(registry_path: Path, runtime: Path) -> None:
    status = collect_status(
        registry_path=registry_path,
        runtime_root_override=str(runtime),
        scan_roots=[],
        limit=5,
    )
    assert status["ok"], status
    latest = status["run_history"]["goals"][0]["latest_runs"][0]
    summary = latest["benchmark_comparison_summary"]
    gate = summary["baseline_failure_gate"]
    assert gate["treatment_eligible"] is True, summary
    assert gate["control_plane_addressable"] is True, summary
    decision = latest["benchmark_comparison_decision_note"]
    assert decision["evidence_layer"] == "baseline_failure_gate", decision
    assert decision["decision"] == "continue", decision
    assert_public_safe(latest)


def assert_codex_goal_mode_fixture(registry_path: Path, runtime: Path) -> None:
    payload = run_cli_json(
        [
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
            "--mode",
            "codex-goal-mode",
            "--dataset",
            BENCHMARK_ID,
            "--include-task-name",
            TASK_ID,
            "--no-global-sync",
        ]
    )
    assert payload["ok"] is True, payload
    assert payload["appended"] is False, payload
    assert payload["classification"] == "terminal_bench_codex_goal_mode_baseline_dry_run_v0", payload
    run = payload["benchmark_run"]
    assert run["mode"] == "codex_goal_mode_baseline_cli_dry_run", run
    assert run["worker_mode"] == "codex_goal_mode_baseline", run
    assert run["loopx_inside_case"] is False, run
    assert run["case_semantics_changed_by_harness"] is False, run
    assert run["official_score_comparable_to_loopx_treatment"] is True, run
    assert run["control_plane_score_applicable"] is False, run
    assert "loopx_mode" not in run["agent"]["kwargs_keys"], run
    assert "codex_goal_mode_invocation_surface" in run["agent"]["kwargs_keys"], run
    assert (
        run["episode_policy"]["schema_version"]
        == "terminal_bench_codex_goal_mode_baseline_episode_policy_v0"
    ), run
    assert run["episode_policy"]["loopx_role"] == "parent_runner_only_compact_ingest", run
    assert run["real_run"] is False, run
    assert run["submit_eligible"] is False, run
    assert_public_safe(payload)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-baseline-gate-") as tmp:
        registry_path, runtime, result_path, run_path = write_fixture(Path(tmp))
        assert_codex_goal_mode_fixture(registry_path, runtime)
        positive = run_cli_json(
            base_args(registry_path, runtime, result_path)
            + [
                "--control-plane-addressable",
                "--same-task-semantics",
                "--same-runner-protocol",
                "--trace-publicness-verified",
            ]
        )
        assert_gate(positive, eligible=True, appended=False)

        negative = run_cli_json(base_args(registry_path, runtime, result_path))
        assert_gate(negative, eligible=False, appended=False)

        run_input = run_cli_json(base_args(registry_path, runtime, run_path))
        assert_gate(
            run_input,
            eligible=False,
            appended=False,
            source="compact_benchmark_run_v0",
        )

        appended = run_cli_json(
            base_args(registry_path, runtime, result_path)
            + [
                "--goal-id",
                GOAL_ID,
                "--control-plane-addressable",
                "--same-task-semantics",
                "--same-runner-protocol",
                "--trace-publicness-verified",
                "--delivery-batch-scale",
                "single_surface",
                "--delivery-outcome",
                "outcome_progress",
                "--execute",
            ]
        )
        assert_gate(appended, eligible=True, appended=True)
        assert_status_projection(registry_path, runtime)

    print("benchmark-baseline-failure-gate-smoke ok")


if __name__ == "__main__":
    main()
