#!/usr/bin/env python3
"""Smoke-test compact benchmark learning ledger routing."""

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

from loopx.benchmark import build_benchmark_learning_ledger  # noqa: E402
from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import collect_status  # noqa: E402


GOAL_ID = "benchmark-learning-ledger-fixture"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def comparison(
    delta: float | str,
    *,
    comparison_id: str,
    failure_labels: list[str] | None = None,
    cost_delta_usd: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "benchmark_comparison_v0",
        "task_id": "terminal-bench@2.0/compact-fixture",
        "comparison_id": comparison_id,
        "benchmark_id": "terminal-bench@2.0",
        "baseline_scenario_id": "hardened-codex",
        "treatment_scenario_id": "codex-loopx",
        "official_task_score_delta": delta,
        "control_plane_score_delta": 0.0,
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "assisted_collaboration_claim_allowed": False,
            "raw_trace_excluded": True,
        },
    }
    if failure_labels:
        payload["failure_attribution_labels"] = failure_labels
    if cost_delta_usd is not None:
        payload["cost_delta_usd"] = cost_delta_usd
    return payload


def benchmark_run(
    mode: str,
    score: float,
    *,
    worker_calls: int = 0,
    first_blocker: str = "",
    failure_labels: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": f"terminal-bench-2-0-compact-fixture-{mode}",
        "mode": mode,
        "real_run": True,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_task_score": {
            "kind": "terminal_bench_verifier_reward",
            "value": score,
            "passed": score >= 1,
        },
        "worker_loopx_cli_call_total": worker_calls,
        "worker_benchmark_run_schema_ok_count": 1 if worker_calls else 0,
        "failure_attribution_labels": failure_labels or [],
        "active_user_observation": {
            "observed_after_worker_start": worker_calls > 0,
        },
        "read_boundary": {
            "raw_artifacts_read": False,
            "task_text_read": False,
        },
    }
    if first_blocker:
        payload["first_blocker"] = first_blocker
    return payload


def test_startup_failure_routes_to_adapter_contract() -> None:
    payload = build_benchmark_learning_ledger(
        comparison(
            -1.0,
            comparison_id="startup-failure",
            failure_labels=["treatment_pre_worker_agent_setup_failed"],
            cost_delta_usd=0.2,
        ),
        benchmark_runs=[
            benchmark_run("hardened-codex", 1.0),
            benchmark_run(
                "codex-loopx",
                0.0,
                first_blocker="pre_worker_agent_setup_failed",
                failure_labels=["treatment_pre_worker_agent_setup_failed"],
            ),
        ],
    )

    assert payload["schema_version"] == "benchmark_learning_ledger_v0", payload
    assert payload["learning_status"] == "generic_loopx_repair_or_attribution_required", payload
    assert "adapter_startup_argument_contract" in payload["repair_candidates"], payload
    assert payload["learning_quota_gate"]["spend_allowed"] is True, payload
    assert payload["routing"]["new_candidate_allowed"] is False, payload
    assert payload["routing"]["next_allowed_action"] == "repair_or_validate_adapter_startup_argument_contract", payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_environment_setup_failure_routes_to_benchmark_environment_contract() -> None:
    payload = build_benchmark_learning_ledger(
        comparison(
            0.0,
            comparison_id="environment-setup-failure",
            failure_labels=["environment_setup_failed_before_worker"],
        ),
        benchmark_runs=[
            benchmark_run("hardened-codex", 0.0),
            benchmark_run(
                "codex-loopx",
                0.0,
                first_blocker="environment_setup_failed_before_worker",
                failure_labels=["environment_setup_failed_before_worker"],
            ),
        ],
    )

    assert payload["schema_version"] == "benchmark_learning_ledger_v0", payload
    assert payload["learning_status"] == "generic_loopx_repair_or_attribution_required", payload
    assert "benchmark_environment_setup_contract" in payload["repair_candidates"], payload
    assert "adapter_startup_argument_contract" not in payload["repair_candidates"], payload
    assert payload["learning_quota_gate"]["spend_allowed"] is True, payload
    assert payload["routing"]["new_candidate_allowed"] is False, payload
    assert payload["routing"]["next_allowed_action"] == (
        "repair_or_validate_benchmark_environment_setup_contract"
    ), payload


def test_materialization_blocker_is_countable_but_not_repeatable() -> None:
    payload = build_benchmark_learning_ledger(
        comparison(
            "no_compact_official_score_available",
            comparison_id="materialization-missing",
            failure_labels=[
                "runner_compact_result_missing",
                "harbor_job_root_missing",
            ],
        ),
        benchmark_runs=[
            benchmark_run(
                "codex-loopx",
                0.0,
                first_blocker="runner_compact_result_missing",
                failure_labels=["runner_compact_result_missing"],
            ),
        ],
    )

    assert payload["lifecycle_gate"]["budget_count_allowed"] is True, payload
    assert payload["learning_quota_gate"]["spend_allowed"] is True, payload
    assert "benchmark_lifecycle_materialization_gate" in payload["repair_candidates"], payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is False, payload


def test_extra_cost_without_gain_routes_to_overhead_guard() -> None:
    payload = build_benchmark_learning_ledger(
        comparison(0.0, comparison_id="costly-no-gain", cost_delta_usd=1.25),
        benchmark_runs=[
            benchmark_run("hardened-codex", 1.0),
            benchmark_run("codex-loopx", 1.0, worker_calls=3),
        ],
    )

    assert payload["overhead"]["label"] == "extra_cost_without_official_gain", payload
    assert "claim_cost_overhead_guard" in payload["repair_candidates"], payload
    assert payload["learning_quota_gate"]["spend_allowed"] is True, payload
    assert payload["learning_status"] == "loop_validation_cost_overhead_guard", payload
    assert payload["claim_strength"] == "loop_validation_no_score_uplift", payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is True, payload
    assert payload["routing"]["next_allowed_action"] == (
        "select_next_candidate_or_add_named_cost_control_hypothesis_before_repeat"
    ), payload


def test_no_learning_signal_blocks_learning_spend() -> None:
    payload = build_benchmark_learning_ledger(
        comparison(0.0, comparison_id="no-gh-signal"),
        benchmark_runs=[
            benchmark_run("hardened-codex", 1.0),
            benchmark_run("codex-loopx", 1.0),
        ],
    )

    assert payload["repair_candidates"] == [], payload
    assert payload["learning_quota_gate"]["spend_allowed"] is False, payload
    assert (
        payload["learning_quota_gate"]["blocked_reason"]
        == "compact_result_has_no_loopx_learning_signal"
    ), payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is False, payload
    assert payload["routing"]["next_allowed_action"] == "stop_without_spend_and_record_no_learning_signal", payload


def test_cli_learning_ledger() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        comparison_path = root / "paired_comparison.compact.json"
        baseline_path = root / "baseline.compact.json"
        treatment_path = root / "treatment.compact.json"
        comparison_path.write_text(
            json.dumps(
                comparison(
                    -1.0,
                    comparison_id="startup-cli",
                    failure_labels=["treatment_pre_worker_agent_setup_failed"],
                )
            ),
            encoding="utf-8",
        )
        baseline_path.write_text(json.dumps(benchmark_run("hardened-codex", 1.0)), encoding="utf-8")
        treatment_path.write_text(
            json.dumps(
                benchmark_run(
                    "codex-loopx",
                    0.0,
                    first_blocker="pre_worker_agent_setup_failed",
                    failure_labels=["treatment_pre_worker_agent_setup_failed"],
                )
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "learning-ledger",
                "--benchmark-comparison-json",
                str(comparison_path),
                "--benchmark-run-json",
                str(baseline_path),
                "--benchmark-run-json",
                str(treatment_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert "adapter_startup_argument_contract" in payload["repair_candidates"], payload
        assert payload["learning_quota_gate"]["spend_allowed"] is True, payload
        assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
        assert str(root) not in result.stdout, result.stdout


def test_cli_require_actionable_learning_blocks_no_signal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        comparison_path = root / "paired_comparison.compact.json"
        baseline_path = root / "baseline.compact.json"
        treatment_path = root / "treatment.compact.json"
        comparison_path.write_text(
            json.dumps(comparison(0.0, comparison_id="no-signal-cli")),
            encoding="utf-8",
        )
        baseline_path.write_text(json.dumps(benchmark_run("hardened-codex", 1.0)), encoding="utf-8")
        treatment_path.write_text(json.dumps(benchmark_run("codex-loopx", 1.0)), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "learning-ledger",
                "--benchmark-comparison-json",
                str(comparison_path),
                "--benchmark-run-json",
                str(baseline_path),
                "--benchmark-run-json",
                str(treatment_path),
                "--require-actionable-learning",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert result.returncode == 1, result.stdout
        assert payload["ok"] is False, payload
        assert payload["learning_quota_gate"]["spend_allowed"] is False, payload
        assert payload["error"] == "compact_result_has_no_loopx_learning_signal", payload
        assert str(root) not in result.stdout, result.stdout


def write_append_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    ledger_path = root / "benchmark_learning_ledger.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-11T00:00:00+00:00\n"
        "---\n\n"
        "# Benchmark Learning Ledger Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Append compact benchmark_learning_ledger_v0 through the CLI.\n\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-11T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-learning-ledger",
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
    ledger = build_benchmark_learning_ledger(
        comparison(
            -1.0,
            comparison_id="append-startup-failure",
            failure_labels=["treatment_pre_worker_agent_setup_failed"],
        ),
        benchmark_runs=[
            benchmark_run("hardened-codex", 1.0),
            benchmark_run(
                "codex-loopx",
                0.0,
                first_blocker="pre_worker_agent_setup_failed",
                failure_labels=["treatment_pre_worker_agent_setup_failed"],
            ),
        ],
    )
    ledger["local_artifact_path"] = str(root / "private" / "raw.log")
    write_json(ledger_path, ledger)
    return registry_path, runtime, ledger_path


def assert_no_private_surface(summary: dict[str, Any]) -> None:
    text = json.dumps(summary, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        "private/raw.log",
        "local_artifact_path",
        "OPENAI" + "_API_KEY",
        "auth.json",
        "sessions/",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def test_cli_append_learning_ledger_to_history() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-learning-ledger-append-") as tmp:
        registry_path, runtime, ledger_path = write_append_fixture(Path(tmp))
        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
        args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-benchmark-learning-ledger",
            "--goal-id",
            GOAL_ID,
            "--benchmark-learning-ledger-json",
            str(ledger_path),
            "--recommended-action",
            "repair or validate adapter startup argument contract before another candidate",
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "primary_goal_outcome",
            "--no-global-sync",
        ]

        dry_run = subprocess.run(
            [sys.executable, "-m", "loopx.cli", *args],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        dry_payload = json.loads(dry_run.stdout)
        assert dry_payload["ok"] is True, dry_payload
        assert dry_payload["dry_run"] is True, dry_payload
        assert dry_payload["appended"] is False, dry_payload
        assert not index_path.exists(), index_path
        assert_no_private_surface(dry_payload["benchmark_learning_ledger"])

        appended = subprocess.run(
            [sys.executable, "-m", "loopx.cli", *args, "--execute"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        append_payload = json.loads(appended.stdout)
        assert append_payload["ok"] is True, append_payload
        assert append_payload["dry_run"] is False, append_payload
        assert append_payload["appended"] is True, append_payload
        assert index_path.exists(), index_path
        assert_no_private_surface(append_payload["benchmark_learning_ledger"])

        records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1, records
        record = records[0]
        assert record["classification"] == "benchmark_learning_ledger_v0", record
        assert_no_private_surface(record["benchmark_learning_ledger"])

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=5,
        )
        assert status["ok"], status
        latest_runs = status["run_history"]["goals"][0]["latest_runs"]
        ledger_run = next(
            run for run in latest_runs if run.get("classification") == "benchmark_learning_ledger_v0"
        )
        summary = ledger_run["benchmark_learning_ledger_summary"]
        assert summary["schema_version"] == "benchmark_learning_ledger_v0", summary
        assert summary["learning_status"] == "generic_loopx_repair_or_attribution_required", summary
        assert "adapter_startup_argument_contract" in summary["repair_candidates"], summary
        assert summary["learning_quota_gate"]["spend_allowed"] is True, summary
        assert summary["routing"]["new_candidate_allowed"] is False, summary
        assert (
            summary["routing"]["next_allowed_action"]
            == "repair_or_validate_adapter_startup_argument_contract"
        ), summary
        assert_no_private_surface(summary)

        packet = build_review_packet(status, goal_id=GOAL_ID)
        handoff = packet["project_agent_handoff"]
        assert "learning=generic_loopx_repair_or_attribution_required" in handoff, handoff
        assert "repair=adapter_startup_argument_contract" in handoff, handoff
        assert "next=repair_or_validate_adapter_startup_argument_contract" in handoff, handoff
        assert_no_private_surface({"handoff": handoff})


def main() -> int:
    test_startup_failure_routes_to_adapter_contract()
    test_environment_setup_failure_routes_to_benchmark_environment_contract()
    test_materialization_blocker_is_countable_but_not_repeatable()
    test_extra_cost_without_gain_routes_to_overhead_guard()
    test_no_learning_signal_blocks_learning_spend()
    test_cli_learning_ledger()
    test_cli_require_actionable_learning_blocks_no_signal()
    test_cli_append_learning_ledger_to_history()
    print("benchmark-learning-ledger-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
