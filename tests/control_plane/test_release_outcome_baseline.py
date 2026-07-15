from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from loopx.control_plane.testing.release_outcome_baseline import (
    build_release_outcome_baseline,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _result(
    *,
    task_id: str,
    arm: str,
    passed: bool = True,
    wall_time_ms: int = 1000,
    cost_usd: float = 1.0,
    erroneous_writes: int = 0,
    interventions: int = 0,
    stop_correct: bool = True,
) -> dict[str, object]:
    return {
        "schema_version": "benchmark_result_v0",
        "task_id": task_id,
        "scenario_id": arm,
        "terminal_state": "completed" if passed else "failed",
        "trace_publicness": "compact_public",
        "official_task_score": {
            "kind": "verifier_reward",
            "aggregation": "final",
            "passed": passed,
            "value": 1.0 if passed else 0.0,
        },
        "counts": {
            "wall_time_ms": wall_time_ms,
            "cost_usd": cost_usd,
            "erroneous_write_count": erroneous_writes,
            "human_intervention_count": interventions,
        },
        "stop_policy_correct": stop_correct,
    }


def _manifest(*, case_count: int = 3, repeats: int = 2) -> dict[str, object]:
    pairs: list[dict[str, object]] = []
    for case_index in range(case_count):
        for repeat_index in range(1, repeats + 1):
            task_id = f"task-{case_index}"
            pairs.append(
                {
                    "case_id": f"case-{case_index}",
                    "repeat_index": repeat_index,
                    "same_task_semantics": True,
                    "same_runner_protocol": True,
                    "same_verifier_contract": True,
                    "same_budget": True,
                    "baseline_result": _result(
                        task_id=task_id,
                        arm="baseline",
                        wall_time_ms=1000,
                        cost_usd=1.0,
                    ),
                    "candidate_result": _result(
                        task_id=task_id,
                        arm="candidate",
                        wall_time_ms=900,
                        cost_usd=0.9,
                    ),
                }
            )
    return {
        "schema_version": "release_outcome_pair_manifest_v0",
        "comparison_kind": "stable_release_vs_candidate",
        "baseline_ref": "release:v0.2.5",
        "candidate_ref": "candidate:compact-guided",
        "policy": {
            "min_distinct_cases": 3,
            "min_repetitions_per_case": 2,
            "max_wall_time_ratio": 1.25,
            "max_cost_ratio": 1.25,
        },
        "pairs": pairs,
    }


def test_release_outcome_baseline_routes_clean_pair_to_owner_review() -> None:
    receipt = build_release_outcome_baseline(_manifest())

    assert receipt["comparison_kind"] == "stable_release_vs_candidate"
    assert receipt["decision"] == "owner_review_required"
    assert receipt["eligible_for_owner_review"] is True
    assert receipt["automatic_release_promotion_allowed"] is False
    assert receipt["coverage"]["distinct_case_count"] == 3
    assert receipt["coverage"]["paired_attempt_count"] == 6
    assert receipt["regressions"] == []
    assert receipt["deltas"]["wall_time_ratio"] == 0.9
    assert receipt["deltas"]["cost_ratio"] == 0.9
    assert receipt["read_boundary"]["model_api_invoked"] is False
    assert receipt["read_boundary"]["benchmark_execution_invoked"] is False
    assert receipt["read_boundary"]["release_mutation_invoked"] is False


def test_release_outcome_baseline_holds_behavior_regressions() -> None:
    manifest = _manifest()
    candidate = manifest["pairs"][0]["candidate_result"]
    candidate["terminal_state"] = "failed"
    candidate["official_task_score"]["passed"] = False
    candidate["official_task_score"]["value"] = 0.0
    candidate["counts"]["erroneous_write_count"] = 1
    candidate["counts"]["human_intervention_count"] = 1
    candidate["stop_policy_correct"] = False

    receipt = build_release_outcome_baseline(manifest)

    assert receipt["decision"] == "hold_regression"
    assert receipt["eligible_for_owner_review"] is False
    assert set(receipt["regressions"]) >= {
        "completion_rate",
        "verifier_pass_rate",
        "erroneous_write_count",
        "human_intervention_count",
        "stop_policy_correct_rate",
    }


def test_release_outcome_baseline_requires_representative_repeats() -> None:
    receipt = build_release_outcome_baseline(_manifest(case_count=2, repeats=1))

    assert receipt["decision"] == "insufficient_evidence"
    assert receipt["eligible_for_owner_review"] is False
    assert receipt["coverage"]["evidence_gaps"] == [
        "insufficient_distinct_cases",
        "insufficient_repetitions_per_case",
    ]


def test_release_outcome_baseline_fails_closed_on_noncompact_or_unpaired_input() -> None:
    noncompact = _manifest()
    noncompact["pairs"][0]["baseline_result"]["private_detail"] = "must-not-pass"
    with pytest.raises(ValueError, match="exact compact benchmark_result_v0"):
        build_release_outcome_baseline(noncompact)

    unpaired = _manifest()
    unpaired["pairs"][0]["same_budget"] = False
    with pytest.raises(ValueError, match="same_budget must be true"):
        build_release_outcome_baseline(unpaired)

    mismatched_task = _manifest()
    mismatched_task["pairs"][0]["candidate_result"]["task_id"] = "other-task"
    with pytest.raises(ValueError, match="same task_id"):
        build_release_outcome_baseline(mismatched_task)

    unstable_case = _manifest()
    unstable_case["pairs"][1]["baseline_result"]["task_id"] = "other-task"
    unstable_case["pairs"][1]["candidate_result"]["task_id"] = "other-task"
    with pytest.raises(ValueError, match="same task_id across repetitions"):
        build_release_outcome_baseline(unstable_case)


def test_release_outcome_baseline_rejects_uplift_or_identity_comparisons() -> None:
    uplift = _manifest()
    uplift["comparison_kind"] = "native_codex_vs_loopx"
    with pytest.raises(
        ValueError, match="comparison_kind must be stable_release_vs_candidate"
    ):
        build_release_outcome_baseline(uplift)

    identity = _manifest()
    identity["candidate_ref"] = identity["baseline_ref"]
    with pytest.raises(ValueError, match="baseline_ref and candidate_ref must differ"):
        build_release_outcome_baseline(identity)


def test_release_outcome_cli_is_read_only_and_optionally_fails_closed(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "release-outcome-baseline",
            "--manifest-json",
            str(manifest_path),
            "--require-owner-review-ready",
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["decision"] == "owner_review_required"
    assert payload["read_boundary"]["local_paths_recorded"] is False
    assert str(tmp_path) not in result.stdout

    insufficient = copy.deepcopy(_manifest())
    insufficient["pairs"] = insufficient["pairs"][:2]
    manifest_path.write_text(json.dumps(insufficient), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "release-outcome-baseline",
            "--manifest-json",
            str(manifest_path),
            "--require-owner-review-ready",
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["decision"] == "insufficient_evidence"
    assert payload["error"] == "insufficient_evidence"

    missing_path = tmp_path / "missing-private-name.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "release-outcome-baseline",
            "--manifest-json",
            str(missing_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"] == "manifest_unreadable"
    assert str(tmp_path) not in result.stdout
