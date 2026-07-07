#!/usr/bin/env python3
"""Smoke-test SkillsBench current ledger aggregation policy."""

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

from loopx.benchmark_ledger import (  # noqa: E402
    BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
    build_benchmark_run_ledger_entry,
    build_benchmark_run_ledger_current_aggregate,
    load_benchmark_run_ledger,
    upsert_benchmark_run_ledger_entry,
)


BENCHMARK_ID = "skillsbench@1.1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_entry(
    *,
    run_id: str,
    case_id: str,
    recorded_at: str,
    score: float | None,
    score_status: str,
    failure_class: str,
    failure_scope: str,
    labels: list[str] | None = None,
    score_failure_attribution: str | None = None,
    failure_attribution_labels: list[str] | None = None,
    official_score_attempt_countable: bool | None = None,
    task_setup_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "run_id": run_id,
        "recorded_at": recorded_at,
        "benchmark_id": BENCHMARK_ID,
        "case_id": case_id,
        "case_ids": [case_id],
        "run_group_id": run_id,
        "arm_id": "codex_app_server_goal",
        "status": "completed" if score is not None else "failed",
        "score_status": score_status,
        "failure_class": failure_class,
        "failure_scope": failure_scope,
        "failure_labels": labels or [],
    }
    if score_failure_attribution is not None:
        entry["score_failure_attribution"] = score_failure_attribution
    if failure_attribution_labels is not None:
        entry["failure_attribution_labels"] = failure_attribution_labels
    if official_score_attempt_countable is not None:
        entry["official_score_attempt_countable"] = official_score_attempt_countable
    if task_setup_preflight is not None:
        entry["task_setup_preflight"] = task_setup_preflight
    if score is not None:
        entry["official_score"] = score
        entry["official_passed"] = score >= 1.0
    return entry


def make_ledger(path: Path) -> None:
    ledger: dict[str, Any] = {
        "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
        "benchmarks": {},
    }
    # A later setup failure must not mask an earlier countable official zero.
    for entry in (
        run_entry(
            run_id="latex-official-zero",
            case_id="latex-formula-extraction",
            recorded_at="2026-07-02T01:00:00+08:00",
            score=0.0,
            score_status="completed",
            failure_class="task_solution_failure",
            failure_scope="solution",
            labels=["official_verifier_solution_failure"],
        ),
        run_entry(
            run_id="latex-later-infra",
            case_id="latex-formula-extraction",
            recorded_at="2026-07-02T02:00:00+08:00",
            score=None,
            score_status="missing",
            failure_class="skillsbench_docker_compose_build_stall_timeout",
            failure_scope="runner_or_setup",
            labels=["setup_runner_infra"],
        ),
        run_entry(
            run_id="manufacturing-no-reward",
            case_id="manufacturing-codebook-normalization",
            recorded_at="2026-07-02T01:10:00+08:00",
            score=None,
            score_status="missing",
            failure_class="verifier_no_reward",
            failure_scope="runner_or_setup",
            labels=["verifier_no_reward"],
        ),
        run_entry(
            run_id="manufacturing-official-zero",
            case_id="manufacturing-codebook-normalization",
            recorded_at="2026-07-02T01:20:00+08:00",
            score=0.0,
            score_status="completed",
            failure_class="task_solution_failure",
            failure_scope="solution",
            labels=["official_verifier_solution_failure"],
        ),
        run_entry(
            run_id="partial-run",
            case_id="lab-unit-harmonization",
            recorded_at="2026-07-02T01:30:00+08:00",
            score=0.5,
            score_status="completed",
            failure_class="task_solution_partial",
            failure_scope="solution",
        ),
        run_entry(
            run_id="pre-bridge-rate-limit-score",
            case_id="fix-erlang-ssh-cve",
            recorded_at="2026-07-02T01:35:00+08:00",
            score=0.0,
            score_status="completed",
            failure_class="skillsbench_codex_cli_goal_uncountable_pre_bridge_rate_limit",
            failure_scope="runner_or_setup",
            score_failure_attribution=(
                "skillsbench_codex_cli_goal_uncountable_pre_bridge_rate_limit"
            ),
        ),
        run_entry(
            run_id="setup-score-missing",
            case_id="fix-druid-loophole-cve",
            recorded_at="2026-07-02T01:40:00+08:00",
            score=None,
            score_status="missing",
            failure_class="skillsbench_compose_setup_blocked_before_agent_rounds",
            failure_scope="score_missing",
        ),
        run_entry(
            run_id="verifier-infra-missing",
            case_id="flink-query",
            recorded_at="2026-07-02T01:42:00+08:00",
            score=None,
            score_status="missing",
            failure_class="none",
            failure_scope="score_missing",
            score_failure_attribution="verifier_infrastructure_failure",
        ),
        run_entry(
            run_id="task-source-preflight-missing",
            case_id="canonical-task-source-preflight",
            recorded_at="2026-07-02T01:44:00+08:00",
            score=None,
            score_status="missing",
            failure_class="none",
            failure_scope="score_missing",
            score_failure_attribution="skillsbench_task_source_preflight_blocked",
        ),
        run_entry(
            run_id="docker-compose-apt-missing",
            case_id="pddl-tpp-planning",
            recorded_at="2026-07-02T01:46:00+08:00",
            score=None,
            score_status="missing",
            failure_class="none",
            failure_scope="score_missing",
            failure_attribution_labels=[
                "skillsbench_docker_compose_apt_repository_failure",
            ],
        ),
        run_entry(
            run_id="reward-missing-attribution",
            case_id="reward-artifact-missing",
            recorded_at="2026-07-02T01:48:00+08:00",
            score=None,
            score_status="missing",
            failure_class="none",
            failure_scope="score_missing",
            score_failure_attribution="verifier_reward_missing",
        ),
        run_entry(
            run_id="sanity-task-preflight",
            case_id="hello-world",
            recorded_at="2026-07-02T01:50:00+08:00",
            score=None,
            score_status="missing",
            failure_class="skillsbench_task_source_preflight_blocked",
            failure_scope="score_missing",
            task_setup_preflight={
                "schema_version": "skillsbench_task_setup_preflight_v0",
                "status": "task_missing_from_canonical_tasks",
                "task_id": "hello-world",
                "canonical_task_present": False,
                "alternate_source_kind": "experiments_sanity_tasks",
                "alternate_source_supported_by_runner": False,
            },
        ),
    ):
        ledger = upsert_benchmark_run_ledger_entry(ledger, entry)
    write_json(path, ledger)


def test_current_aggregate_prefers_countable_results() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-current-aggregate-") as tmp:
        root = Path(tmp)
        ledger_path = root / "benchmark-run-ledger.json"
        make_ledger(ledger_path)
        ledger = load_benchmark_run_ledger(ledger_path)
        aggregate = build_benchmark_run_ledger_current_aggregate(
            ledger,
            benchmark_id=BENCHMARK_ID,
            canonical_case_ids=[
                "latex-formula-extraction",
                "manufacturing-codebook-normalization",
                "lab-unit-harmonization",
                "fix-druid-loophole-cve",
                "flink-query",
                "canonical-task-source-preflight",
                "pddl-tpp-planning",
                "reward-artifact-missing",
                "fix-erlang-ssh-cve",
                "hello-world",
                "never-run-case",
            ],
        )
        assert aggregate["canonical_covered"] == 9, aggregate
        assert aggregate["distribution"] == {
            "missing": 1,
            "official_zero": 2,
            "partial": 1,
            "pass": 0,
            "setup_runner_infra": 4,
            "uncountable_official_score": 1,
            "verifier_no_reward": 1,
        }, aggregate
        assert aggregate["countable_score_summary"] == {
            "schema_version": "benchmark_run_ledger_countable_score_summary_v0",
            "countable_case_count": 3,
            "countable_score_sum": 0.5,
            "countable_score_mean": 0.166667,
            "pass_count": 0,
            "partial_count": 1,
            "official_zero_count": 2,
            "uncountable_numeric_case_count": 1,
            "countable_case_ids": [
                "lab-unit-harmonization",
                "latex-formula-extraction",
                "manufacturing-codebook-normalization",
            ],
            "uncountable_numeric_case_ids": ["fix-erlang-ssh-cve"],
        }, aggregate["countable_score_summary"]
        assert (
            aggregate["case_best"]["latex-formula-extraction"]["run_id"]
            == "latex-official-zero"
        ), aggregate["case_best"]["latex-formula-extraction"]
        assert (
            aggregate["case_best"]["manufacturing-codebook-normalization"]["run_id"]
            == "manufacturing-official-zero"
        ), aggregate["case_best"]["manufacturing-codebook-normalization"]
        assert aggregate["case_best"]["flink-query"]["effective_failure_class"] == (
            "verifier_infrastructure_failure"
        )
        assert aggregate["case_best"]["pddl-tpp-planning"]["effective_failure_class"] == (
            "skillsbench_docker_compose_apt_repository_failure"
        )
        assert aggregate["case_best"]["reward-artifact-missing"]["bucket"] == (
            "verifier_no_reward"
        )
        assert aggregate["case_best"]["fix-erlang-ssh-cve"]["bucket"] == (
            "uncountable_official_score"
        )
        assert aggregate["case_best"]["fix-erlang-ssh-cve"][
            "official_score_countable"
        ] is False
        assert aggregate["case_best"]["fix-erlang-ssh-cve"][
            "official_score_countability_reason"
        ] == "uncountable_attribution"
        assert "hello-world" not in aggregate["case_best"], aggregate["case_best"]
        assert "hello-world" not in aggregate["cases_by_bucket"]["setup_runner_infra"]


def test_ledger_marks_uncountable_numeric_scores_noncountable() -> None:
    pre_bridge_rate_limit = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": BENCHMARK_ID,
        "case_id": "fix-erlang-ssh-cve",
        "job_name": "skillsbench_1_1_fix_erlang_ssh_cve_codex_cli_goal_baseline",
        "route": "codex-cli-goal-baseline",
        "official_score_status": "completed",
        "official_score": 0.0,
        "score_failure_attribution": (
            "skillsbench_codex_cli_goal_uncountable_pre_bridge_rate_limit"
        ),
    }
    entry = build_benchmark_run_ledger_entry(pre_bridge_rate_limit)
    assert entry["official_score"] == 0.0, entry
    assert entry["score_failure_attribution"] == (
        "skillsbench_codex_cli_goal_uncountable_pre_bridge_rate_limit"
    ), entry
    assert entry["official_score_countable"] is False, entry
    assert entry["official_score_countability_reason"] == "uncountable_attribution", entry
    assert "countable_score" not in entry, entry

    explicit_noncountable = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": BENCHMARK_ID,
        "case_id": "goal-active-timeout",
        "job_name": "skillsbench_1_1_goal_active_timeout_codex_cli_goal_baseline",
        "route": "codex-cli-goal-baseline",
        "official_score_status": "completed",
        "official_score": 0.0,
        "official_score_attempt_countable": False,
    }
    entry = build_benchmark_run_ledger_entry(explicit_noncountable)
    assert entry["official_score_attempt_countable"] is False, entry
    assert entry["official_score_countable"] is False, entry
    assert entry["official_score_countability_reason"] == (
        "official_score_attempt_not_countable"
    ), entry


def test_current_aggregate_default_inference_excludes_sanity_sources() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-current-aggregate-default-") as tmp:
        ledger_path = Path(tmp) / "benchmark-run-ledger.json"
        make_ledger(ledger_path)
        ledger = load_benchmark_run_ledger(ledger_path)
        aggregate = build_benchmark_run_ledger_current_aggregate(
            ledger,
            benchmark_id=BENCHMARK_ID,
        )
        assert aggregate["canonical_total"] == 9, aggregate
        assert aggregate["canonical_covered"] == 9, aggregate
        assert aggregate["distribution"]["setup_runner_infra"] == 4, aggregate
        assert aggregate["distribution"]["verifier_no_reward"] == 1, aggregate
        assert aggregate["distribution"]["uncountable_official_score"] == 1, aggregate
        assert aggregate["countable_score_summary"]["countable_case_count"] == 3, aggregate
        assert aggregate["countable_score_summary"]["countable_score_mean"] == 0.166667, aggregate
        assert "hello-world" not in aggregate["case_best"], aggregate["case_best"]
        assert "hello-world" not in aggregate["cases_by_bucket"]["setup_runner_infra"]


def test_current_aggregate_cli_writes_public_safe_json() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-current-aggregate-cli-") as tmp:
        root = Path(tmp)
        ledger_path = root / "benchmark-run-ledger.json"
        output_path = root / "current-aggregate-status.json"
        canonical_root = root / "skillsbench" / "tasks"
        make_ledger(ledger_path)
        for case_id in [
            "latex-formula-extraction",
            "manufacturing-codebook-normalization",
            "lab-unit-harmonization",
            "fix-druid-loophole-cve",
            "never-run-case",
        ]:
            (canonical_root / case_id).mkdir(parents=True, exist_ok=True)
        (root / "skillsbench" / "experiments" / "sanity-tasks" / "hello-world").mkdir(
            parents=True,
            exist_ok=True,
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "run-ledger-aggregate",
                "--run-ledger-path",
                str(ledger_path),
                "--benchmark-id",
                BENCHMARK_ID,
                "--canonical-case-root",
                str(canonical_root),
                "--output-json",
                str(output_path),
                "--execute",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert output_path.exists(), payload
        aggregate = json.loads(output_path.read_text(encoding="utf-8"))
        assert aggregate["canonical_total"] == 5, aggregate
        assert aggregate["case_best"]["latex-formula-extraction"]["bucket"] == "official_zero"
        assert aggregate["case_best"]["fix-druid-loophole-cve"]["bucket"] == "setup_runner_infra"
        assert aggregate["countable_score_summary"]["countable_case_count"] == 3
        assert aggregate["countable_score_summary"]["countable_score_mean"] == 0.166667
        assert "hello-world" not in aggregate["case_best"]
        assert aggregate["selection_policy"]["source_paths_recorded"] is False
        assert ".local" not in output_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_current_aggregate_prefers_countable_results()
    test_ledger_marks_uncountable_numeric_scores_noncountable()
    test_current_aggregate_default_inference_excludes_sanity_sources()
    test_current_aggregate_cli_writes_public_safe_json()
    print("skillsbench-current-ledger-aggregate-smoke: ok")
