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
            run_id="setup-score-missing",
            case_id="fix-druid-loophole-cve",
            recorded_at="2026-07-02T01:40:00+08:00",
            score=None,
            score_status="missing",
            failure_class="skillsbench_compose_setup_blocked_before_agent_rounds",
            failure_scope="score_missing",
        ),
        run_entry(
            run_id="sanity-task-preflight",
            case_id="hello-world",
            recorded_at="2026-07-02T01:50:00+08:00",
            score=None,
            score_status="missing",
            failure_class="skillsbench_task_source_preflight_blocked",
            failure_scope="score_missing",
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
                "never-run-case",
            ],
        )
        assert aggregate["canonical_covered"] == 4, aggregate
        assert aggregate["distribution"] == {
            "missing": 1,
            "official_zero": 2,
            "partial": 1,
            "pass": 0,
            "setup_runner_infra": 1,
            "verifier_no_reward": 0,
        }, aggregate
        assert (
            aggregate["case_best"]["latex-formula-extraction"]["run_id"]
            == "latex-official-zero"
        ), aggregate["case_best"]["latex-formula-extraction"]
        assert (
            aggregate["case_best"]["manufacturing-codebook-normalization"]["run_id"]
            == "manufacturing-official-zero"
        ), aggregate["case_best"]["manufacturing-codebook-normalization"]
        assert "hello-world" not in aggregate["case_best"], aggregate["case_best"]


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
        assert "hello-world" not in aggregate["case_best"]
        assert aggregate["selection_policy"]["source_paths_recorded"] is False
        assert ".local" not in output_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_current_aggregate_prefers_countable_results()
    test_current_aggregate_cli_writes_public_safe_json()
    print("skillsbench-current-ledger-aggregate-smoke: ok")
