#!/usr/bin/env python3
"""Smoke-test operator-simulator rows in the common benchmark run ledger."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_ledger import load_benchmark_run_ledger, update_benchmark_run_ledger


BENCHMARK_ID = "operator-simulator-ledger@v0"
CASE_ID = "minimal-assisted-case"


def main() -> None:
    operator_run = {
        "schema_version": "operator_simulator_run_v0",
        "benchmark_id": BENCHMARK_ID,
        "case_id": CASE_ID,
        "mode": "assisted_operator_simulator",
        "simulator_setting": "deterministic_operator_fixture",
        "intervention_count": 1,
        "proactive_intervention_count": 1,
        "assisted_score": 0.75,
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "leaderboard_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "assisted_score_kept_separate_from_official": True,
        },
    }
    benchmark_run = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "operator_simulator_ledger_smoke",
        "benchmark_id": BENCHMARK_ID,
        "case_id": CASE_ID,
        "job_name": "operator_simulator_ledger_fixture",
        "mode": "assisted_operator_simulator",
        "route": "operator-simulator-ledger-fixture",
        "runner_return_status": "completed",
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "operator_simulator_run": operator_run,
    }

    with tempfile.TemporaryDirectory(prefix="benchmark-run-ledger-operator-simulator-") as tmp:
        ledger_path = Path(tmp) / "benchmark-run-ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=benchmark_run,
            run_group_id="operator-simulator-ledger-fixture",
            arm_id="deterministic_operator_fixture",
            dry_run=False,
        )
        assert update["updated"] is True, update
        entry = update["entry"]
        assert entry["score_status"] == "missing", entry

        ledger = load_benchmark_run_ledger(ledger_path)
        run = ledger["benchmarks"][BENCHMARK_ID]["cases"][CASE_ID]["runs"][0]
        for record in (entry, run):
            compact = record["operator_simulator_run"]
            assert "official_score" not in record, record
            assert "official_score" not in compact, compact
            assert compact["schema_version"] == "operator_simulator_run_v0", compact
            assert compact["assisted_score"] == 0.75, compact
            assert compact["official_score_claim_allowed"] is False, compact
            assert compact["assisted_score_kept_separate_from_official"] is True, compact

    print("benchmark-run-ledger-operator-simulator-smoke ok")


if __name__ == "__main__":
    main()
