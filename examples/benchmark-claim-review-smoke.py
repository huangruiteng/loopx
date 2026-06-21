#!/usr/bin/env python3
"""Smoke-test compact benchmark claim review."""

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

from loopx.benchmark import (  # noqa: E402
    build_benchmark_claim_review,
    build_benchmark_verifier_attribution_review,
)


def comparison(delta: float, *, comparison_id: str = "fixture-pair") -> dict[str, Any]:
    return {
        "schema_version": "benchmark_comparison_v0",
        "task_id": "terminal-bench@2.0/db-wal-recovery",
        "comparison_id": comparison_id,
        "benchmark_id": "terminal-bench@2.0",
        "baseline_scenario_id": "hardened-codex",
        "treatment_scenario_id": "codex-loopx",
        "official_task_score_delta": delta,
        "control_plane_score_delta": 0.75,
        "both_success": delta == 0,
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "raw_trace_excluded": True,
        },
    }


def benchmark_run(
    mode: str,
    score: float,
    *,
    worker_calls: int = 0,
    attribution: str = "none",
    labels: list[str] | None = None,
    exception_type: str | None = None,
    worker_start_status: str | None = None,
    startup_blocker: str | None = None,
    runner_return_status: str | None = None,
    official_score_status: str | None = None,
    progress: dict[str, int] | None = None,
    verifier_reward_present: bool | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": f"terminal-bench-2-0-db-wal-recovery-{mode}",
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
        "score_failure_attribution": attribution,
        "failure_attribution_labels": labels or [],
        "active_user_observation": {
            "observed_after_worker_start": worker_calls > 0,
        },
        "read_boundary": {
            "raw_artifacts_read": False,
            "task_text_read": False,
        },
    }
    if runner_return_status:
        payload["runner_return_status"] = runner_return_status
    if official_score_status:
        payload["official_score_status"] = official_score_status
    if progress:
        payload["progress"] = progress
    if startup_blocker:
        payload.update(
            {
                "worker_startup_blocker_count": 1,
                "worker_bridge_materialization_status": (
                    "pre_worker_startup_blocker_recorded"
                ),
                "worker_bridge_materialization_blocker": startup_blocker,
                "pre_worker_startup_blocker": startup_blocker,
                "worker_bridge_outcome": {
                    "worker_startup_blocker_count": 1,
                    "worker_bridge_materialization_status": (
                        "pre_worker_startup_blocker_recorded"
                    ),
                    "worker_bridge_materialization_blocker": startup_blocker,
                    "pre_worker_startup_blocker": startup_blocker,
                },
            }
        )
    if exception_type or worker_start_status or verifier_reward_present is not None:
        payload["trials"] = [
            {
                "task_id": "db-wal-recovery",
                "exception_type": exception_type or "none",
                "reward": {"reward": score},
                **(
                    {"worker_start_status": worker_start_status}
                    if worker_start_status
                    else {}
                ),
                **(
                    {"verifier_reward_present": verifier_reward_present}
                    if verifier_reward_present is not None
                    else {}
                ),
            }
        ]
    return payload


def test_candidate_with_baseline_attribution_caveat() -> None:
    baseline = benchmark_run(
        "hardened-codex",
        0.0,
        attribution="verifier_platform_probe_failure",
        labels=["verifier_platform_probe_failure"],
    )
    treatment = benchmark_run("codex-loopx", 1.0, worker_calls=4)
    payload = build_benchmark_claim_review(
        comparison(1.0),
        benchmark_runs=[baseline, treatment],
    )
    decision = payload["decision"]

    assert payload["schema_version"] == "benchmark_claim_review_v0", payload
    assert payload["official_task_score_delta"] == 1.0, payload
    assert payload["treatment_worker_evidence"]["present"] is True, payload
    assert payload["baseline_score_failure_attribution"] == "verifier_platform_probe_failure", payload
    assert "baseline_failure_attribution_caveat" in decision["blockers"], payload
    assert decision["validation_enhancement_candidate"] is True, payload
    assert decision["clean_validation_enhancement"] is False, payload
    assert decision["claim_strength"] == "candidate_score_recovery_needs_attribution_review", payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_loop_validation_without_score_uplift() -> None:
    baseline = benchmark_run("hardened-codex", 1.0)
    treatment = benchmark_run("codex-loopx", 1.0, worker_calls=3)
    payload = build_benchmark_claim_review(
        comparison(0.0, comparison_id="no-delta-pair"),
        benchmark_runs=[baseline, treatment],
    )
    decision = payload["decision"]

    assert decision["claim_strength"] == "loop_validation_no_score_uplift", payload
    assert decision["validation_enhancement_candidate"] is False, payload
    assert "no_positive_official_task_score_delta" in decision["blockers"], payload


def test_claim_review_derives_compact_agent_timeout_attribution() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        exception_type="AgentTimeoutError",
    )
    treatment = benchmark_run(
        "codex-loopx",
        0.0,
        worker_calls=2,
        exception_type="AgentTimeoutError",
    )
    payload = build_benchmark_claim_review(
        comparison(0.0, comparison_id="timeout-no-uplift"),
        benchmark_runs=[baseline, treatment],
    )

    assert payload["decision"]["claim_strength"] == "loop_validation_no_score_uplift", payload
    assert payload["baseline_score_failure_attribution"] == "agent_timeout_score_failure", payload
    assert "agent_timeout_before_solution_completion" in payload[
        "baseline_failure_attribution_labels"
    ], payload
    assert payload["decision"]["blockers"] == ["no_positive_official_task_score_delta"], payload
    assert payload["treatment_worker_evidence"]["present"] is True, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_claim_review_derives_compact_agent_setup_timeout_attribution() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        exception_type="AgentSetupTimeoutError",
    )
    treatment = benchmark_run(
        "codex-loopx",
        0.0,
        worker_calls=0,
        exception_type="AgentSetupTimeoutError",
    )
    payload = build_benchmark_claim_review(
        comparison(0.0, comparison_id="setup-timeout-no-uplift"),
        benchmark_runs=[baseline, treatment],
    )

    assert payload["decision"]["claim_strength"] == "no_validation_enhancement", payload
    assert payload["baseline_score_failure_attribution"] == (
        "agent_setup_timeout_score_failure"
    ), payload
    assert "agent_setup_timeout_before_worker_start" in payload[
        "baseline_failure_attribution_labels"
    ], payload
    assert payload["decision"]["blockers"] == ["no_positive_official_task_score_delta"], payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_claim_review_derives_worker_start_setup_attribution() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        exception_type="NonZeroAgentExitCodeError",
        worker_start_status="pre_worker_agent_setup_failed",
    )
    treatment = benchmark_run("codex-loopx", 0.0, worker_calls=0)
    payload = build_benchmark_claim_review(
        comparison(0.0, comparison_id="worker-start-setup-failure"),
        benchmark_runs=[baseline, treatment],
    )

    assert payload["baseline_score_failure_attribution"] == (
        "agent_setup_score_failure"
    ), payload
    assert "agent_setup_failed_before_worker_start" in payload[
        "baseline_failure_attribution_labels"
    ], payload
    assert "baseline_failure_attribution_caveat" not in payload["decision"][
        "blockers"
    ], payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_cli_review_claim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        comparison_path = root / "paired_comparison.compact.json"
        baseline_path = root / "baseline.compact.json"
        treatment_path = root / "treatment.compact.json"
        comparison_path.write_text(json.dumps(comparison(1.0)), encoding="utf-8")
        baseline_path.write_text(
            json.dumps(
                benchmark_run(
                    "hardened-codex",
                    0.0,
                    attribution="verifier_platform_probe_failure",
                    labels=["verifier_platform_probe_failure"],
                )
            ),
            encoding="utf-8",
        )
        treatment_path.write_text(
            json.dumps(benchmark_run("codex-loopx", 1.0, worker_calls=4)),
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
                "review-claim",
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
        assert payload["decision"]["claim_strength"] == "candidate_score_recovery_needs_attribution_review", payload
        assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
        assert str(root) not in result.stdout, result.stdout


def test_verifier_attribution_keeps_compact_caveat() -> None:
    baseline = benchmark_run(
        "hardened-codex",
        0.0,
        attribution="verifier_platform_probe_failure",
        labels=["verifier_platform_probe_failure"],
    )
    treatment = benchmark_run("codex-loopx", 1.0, worker_calls=4)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )
    decision = payload["decision"]

    assert payload["schema_version"] == "benchmark_verifier_attribution_review_v0", payload
    assert payload["reviewed_run_count"] == 2, payload
    assert decision["baseline_claim_caveat_resolved"] is False, payload
    assert "baseline_verifier_attribution_caveat" in decision["blockers"], payload
    assert payload["routing"]["treatment_eligible"] is False, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is True, payload
    assert payload["routing"]["requires_verifier_preflight_repair"] is True, payload
    assert payload["routing"]["next_allowed_action"] == (
        "repair_verifier_preflight_or_select_new_material_ready_case"
    ), payload
    assert payload["routing"]["blocked_action_scope"] == (
        "treatment_and_same_task_repeat"
    ), payload
    assert (
        payload["run_reviews"][0]["attribution_class"]
        == "verifier_platform_probe_failure"
    ), payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_resolves_explicit_model_failure() -> None:
    baseline = benchmark_run(
        "hardened-codex",
        0.0,
        attribution="model_solution_failure",
        labels=[],
    )
    treatment = benchmark_run("codex-loopx", 1.0, worker_calls=4)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    assert payload["decision"]["baseline_claim_caveat_resolved"] is True, payload
    assert payload["decision"]["clean_model_failure_attribution"] is True, payload
    assert payload["decision"]["blockers"] == [], payload
    assert payload["routing"]["treatment_eligible"] is True, payload
    assert payload["routing"]["repeat_allowed"] is True, payload
    assert payload["routing"]["new_candidate_allowed"] is True, payload
    assert payload["routing"]["requires_verifier_preflight_repair"] is False, payload
    assert payload["routing"]["next_allowed_action"] == (
        "baseline_failure_is_control_plane_addressable"
    ), payload
    assert payload["run_reviews"][0]["attribution_class"] == "model_or_solution_failure", payload


def test_verifier_attribution_resolves_compact_agent_timeout() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        exception_type="AgentTimeoutError",
    )
    treatment = benchmark_run(
        "codex-loopx",
        0.0,
        worker_calls=2,
        exception_type="AgentTimeoutError",
    )

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert payload["decision"]["baseline_claim_caveat_resolved"] is True, payload
    assert payload["decision"]["clean_model_failure_attribution"] is True, payload
    assert payload["decision"]["blockers"] == [], payload
    assert baseline_review["attribution_class"] == "agent_timeout_score_failure", payload
    assert baseline_review["agent_timeout_count"] == 1, payload
    assert "agent_timeout_before_solution_completion" in baseline_review[
        "failure_attribution_labels"
    ], payload
    assert payload["routing"]["treatment_eligible"] is True, payload
    assert payload["routing"]["repeat_allowed"] is True, payload
    assert payload["routing"]["new_candidate_allowed"] is True, payload
    assert payload["routing"]["requires_finer_compact_attribution"] is False, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_routes_generic_agent_exception_to_case_research() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        exception_type="RuntimeError",
        verifier_reward_present=False,
    )
    treatment = benchmark_run(
        "codex-loopx",
        0.0,
        worker_calls=2,
        exception_type="RuntimeError",
        verifier_reward_present=False,
    )

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert payload["decision"]["baseline_claim_caveat_resolved"] is True, payload
    assert payload["decision"]["blockers"] == [], payload
    assert baseline_review["attribution_class"] == "agent_exception_score_failure", (
        payload
    )
    assert baseline_review["agent_exception_count"] == 1, payload
    assert "agent_exception_before_solution_completion" in baseline_review[
        "failure_attribution_labels"
    ], payload
    assert payload["routing"]["treatment_eligible"] is False, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is True, payload
    assert payload["routing"]["requires_case_exception_research"] is True, payload
    assert payload["routing"]["next_allowed_action"] == (
        "inspect_compact_agent_exception_before_same_task_repeat"
    ), payload
    assert payload["routing"]["blocked_action_scope"] == (
        "same_task_repeat_until_exception_hypothesis"
    ), payload


def test_verifier_attribution_routes_agent_setup_timeout_to_startup_repair() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        exception_type="AgentSetupTimeoutError",
    )
    treatment = benchmark_run(
        "codex-loopx",
        0.0,
        worker_calls=0,
        exception_type="AgentSetupTimeoutError",
    )

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert payload["decision"]["baseline_claim_caveat_resolved"] is True, payload
    assert payload["decision"]["blockers"] == [], payload
    assert baseline_review["attribution_class"] == (
        "agent_setup_timeout_score_failure"
    ), payload
    assert baseline_review["agent_setup_timeout_count"] == 1, payload
    assert "agent_setup_timeout_before_worker_start" in baseline_review[
        "failure_attribution_labels"
    ], payload
    assert payload["routing"]["treatment_eligible"] is False, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is True, payload
    assert payload["routing"]["requires_agent_setup_repair"] is True, payload
    assert payload["routing"]["requires_finer_compact_attribution"] is False, payload
    assert payload["routing"]["next_allowed_action"] == (
        "repair_agent_setup_timeout_or_select_new_material_ready_case"
    ), payload
    assert payload["routing"]["blocked_action_scope"] == (
        "same_task_repeat_until_setup_repair"
    ), payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_uses_compact_worker_start_status() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        exception_type="NonZeroAgentExitCodeError",
        worker_start_status="pre_worker_agent_setup_failed",
    )
    treatment = benchmark_run("codex-loopx", 0.0, worker_calls=0)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert payload["decision"]["baseline_claim_caveat_resolved"] is True, payload
    assert "baseline_score_failure_unattributed" not in payload["decision"][
        "blockers"
    ], payload
    assert baseline_review["attribution_class"] == (
        "agent_setup_score_failure"
    ), payload
    assert baseline_review["agent_setup_failure_count"] == 1, payload
    assert "agent_setup_failed_before_worker_start" in baseline_review[
        "failure_attribution_labels"
    ], payload
    assert payload["routing"]["requires_agent_setup_repair"] is True, payload
    assert payload["routing"]["requires_finer_compact_attribution"] is False, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_uses_startup_blocker_status() -> None:
    baseline = benchmark_run(
        "hardened-codex",
        0.0,
        startup_blocker="codex_cli_not_on_path",
    )
    treatment = benchmark_run("codex-loopx", 0.0)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert payload["decision"]["baseline_claim_caveat_resolved"] is True, payload
    assert "baseline_score_failure_unattributed" not in payload["decision"][
        "blockers"
    ], payload
    assert baseline_review["attribution_class"] == (
        "agent_setup_score_failure"
    ), payload
    assert "pre_worker_startup_blocker_recorded" in baseline_review[
        "failure_attribution_labels"
    ], payload
    assert payload["routing"]["requires_agent_setup_repair"] is True, payload
    assert payload["routing"]["requires_finer_compact_attribution"] is False, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_routes_worker_self_validation_mismatch() -> None:
    baseline = benchmark_run(
        "codex-loopx",
        0.0,
        attribution="worker_self_validation_official_score_mismatch",
        labels=["worker_self_validation_official_score_mismatch"],
    )
    treatment = benchmark_run("codex-loopx", 0.0, worker_calls=2)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert baseline_review["attribution_class"] == (
        "worker_self_validation_official_score_mismatch"
    ), payload
    assert "baseline_worker_verifier_alignment_caveat" in payload["decision"][
        "blockers"
    ], payload
    assert payload["routing"]["requires_worker_verifier_alignment"] is True, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is False, payload
    assert payload["routing"]["next_allowed_action"] == (
        "align_worker_self_validation_with_official_verifier"
    ), payload
    assert payload["routing"]["blocked_action_scope"] == (
        "same_task_repeat_until_worker_verifier_alignment"
    ), payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_routes_worker_validation_scope_ambiguous() -> None:
    baseline = benchmark_run(
        "codex-loopx",
        0.0,
        attribution="worker_validation_scope_ambiguous_official_score_failure",
        labels=["worker_validation_scope_ambiguous_official_score_failure"],
    )
    treatment = benchmark_run("codex-loopx", 0.0, worker_calls=2)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert baseline_review["attribution_class"] == (
        "worker_validation_scope_ambiguous_official_score_failure"
    ), payload
    assert "baseline_worker_validation_scope_ambiguous_caveat" in payload[
        "decision"
    ]["blockers"], payload
    assert payload["routing"]["requires_worker_validation_scope"] is True, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is False, payload
    assert payload["routing"]["next_allowed_action"] == (
        "add_worker_validation_scope_and_claim_boundary"
    ), payload
    assert payload["routing"]["blocked_action_scope"] == (
        "same_task_repeat_until_worker_validation_scope"
    ), payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_routes_clean_runner_zero_to_finer_compact() -> None:
    baseline = benchmark_run(
        "codex-goal-mode",
        0.0,
        runner_return_status="completed",
        official_score_status="completed",
        progress={
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_pending_trials": 0,
            "n_running_trials": 0,
        },
        verifier_reward_present=True,
    )
    treatment = benchmark_run("codex-loopx", 1.0, worker_calls=2)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    baseline_review = payload["run_reviews"][0]
    assert baseline_review["attribution_class"] == (
        "runner_completed_official_score_zero_unattributed"
    ), payload
    assert baseline_review["runner_completed_score_zero_signal"]["detected"] is True, payload
    assert "baseline_score_failure_unattributed" in payload["decision"][
        "blockers"
    ], payload
    assert payload["routing"]["requires_finer_compact_attribution"] is True, payload
    assert payload["routing"]["treatment_eligible"] is False, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is False, payload
    assert payload["routing"]["next_allowed_action"] == (
        "collect_finer_compact_failure_attribution"
    ), payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_verifier_attribution_all_passed_moves_to_new_candidate() -> None:
    baseline = benchmark_run("codex-goal-mode", 1.0)
    treatment = benchmark_run("codex-loopx", 1.0, worker_calls=2)

    payload = build_benchmark_verifier_attribution_review(
        benchmark_runs=[baseline, treatment],
    )

    assert payload["decision"]["baseline_claim_caveat_resolved"] is False, payload
    assert payload["decision"]["clean_model_failure_attribution"] is False, payload
    assert payload["decision"]["blockers"] == [], payload
    assert payload["routing"]["treatment_eligible"] is False, payload
    assert payload["routing"]["repeat_allowed"] is False, payload
    assert payload["routing"]["new_candidate_allowed"] is True, payload
    assert payload["routing"]["requires_verifier_preflight_repair"] is False, payload
    assert payload["routing"]["next_allowed_action"] == (
        "select_new_material_ready_case_no_score_failure"
    ), payload
    assert payload["routing"]["blocked_action_scope"] == "same_task_claim", payload
    assert payload["run_reviews"][0]["attribution_class"] == "no_score_failure", payload


def test_cli_review_verifier_attribution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_path = root / "baseline.compact.json"
        treatment_path = root / "treatment.compact.json"
        baseline_path.write_text(
            json.dumps(
                benchmark_run(
                    "hardened-codex",
                    0.0,
                    attribution="verifier_platform_probe_failure",
                    labels=["verifier_platform_probe_failure"],
                )
            ),
            encoding="utf-8",
        )
        treatment_path.write_text(
            json.dumps(benchmark_run("codex-loopx", 1.0, worker_calls=4)),
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
                "review-verifier-attribution",
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
        assert payload["decision"]["baseline_claim_caveat_resolved"] is False, payload
        assert "baseline_verifier_attribution_caveat" in payload["decision"]["blockers"], payload
        assert payload["routing"]["treatment_eligible"] is False, payload
        assert payload["routing"]["repeat_allowed"] is False, payload
        assert payload["routing"]["new_candidate_allowed"] is True, payload
        assert payload["routing"]["requires_verifier_preflight_repair"] is True, payload
        assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
        assert str(root) not in result.stdout, result.stdout


def main() -> int:
    test_candidate_with_baseline_attribution_caveat()
    test_loop_validation_without_score_uplift()
    test_claim_review_derives_compact_agent_timeout_attribution()
    test_claim_review_derives_compact_agent_setup_timeout_attribution()
    test_claim_review_derives_worker_start_setup_attribution()
    test_cli_review_claim()
    test_verifier_attribution_keeps_compact_caveat()
    test_verifier_attribution_resolves_explicit_model_failure()
    test_verifier_attribution_resolves_compact_agent_timeout()
    test_verifier_attribution_routes_generic_agent_exception_to_case_research()
    test_verifier_attribution_routes_agent_setup_timeout_to_startup_repair()
    test_verifier_attribution_uses_compact_worker_start_status()
    test_verifier_attribution_uses_startup_blocker_status()
    test_verifier_attribution_routes_worker_self_validation_mismatch()
    test_verifier_attribution_routes_worker_validation_scope_ambiguous()
    test_verifier_attribution_routes_clean_runner_zero_to_finer_compact()
    test_verifier_attribution_all_passed_moves_to_new_candidate()
    test_cli_review_verifier_attribution()
    print("benchmark-claim-review-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
