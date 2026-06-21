#!/usr/bin/env python3
"""Smoke-test compact benchmark runner-owned invariant review."""

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

from loopx.benchmark import build_benchmark_runner_invariant_review  # noqa: E402
from loopx.status import compact_benchmark_run  # noqa: E402


def benchmark_run(
    *,
    submit_eligible: bool = False,
    leaderboard_evidence: bool = False,
    raw_artifacts_read: bool = False,
    task_text_read: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "worker-bridge",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "terminal-bench-2-0-runner-invariant-fixture",
        "mode": "codex-loopx",
        "real_run": True,
        "submit_eligible": submit_eligible,
        "leaderboard_evidence": leaderboard_evidence,
        "official_task_score": {
            "kind": "terminal_bench_verifier_reward",
            "value": 0.0,
            "passed": False,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": raw_artifacts_read,
            "task_text_read": task_text_read,
            "local_paths_recorded": False,
        },
        "validation": {
            "worker_benchmark_run_schema_ok": True,
        },
        "trials": [
            {
                "task_id": "public-fixture-task",
                "trial_name": "fixture-trial",
                "reward": {"reward": 0.0},
            }
        ],
        "private_raw_log_path": "/tmp/private/raw/trajectory.json",
    }


def compact(run: dict[str, Any]) -> dict[str, Any]:
    payload = compact_benchmark_run(run)
    assert payload is not None, run
    return payload


def test_clean_runner_owned_boundary() -> None:
    payload = build_benchmark_runner_invariant_review(compact(benchmark_run()))

    assert payload["schema_version"] == "benchmark_runner_invariant_review_v0", payload
    assert payload["classification"] == "runner_owned_boundary_ok", payload
    assert payload["clean"] is True, payload
    assert payload["mismatch_count"] == 0, payload
    assert payload["missing_field_count"] == 0, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
    assert "private_raw_log_path" not in json.dumps(payload), payload
    assert "/tmp/private" not in json.dumps(payload), payload


def test_worker_cannot_widen_runner_owned_boundary() -> None:
    payload = build_benchmark_runner_invariant_review(
        compact(
            benchmark_run(
                submit_eligible=True,
                leaderboard_evidence=True,
                raw_artifacts_read=True,
                task_text_read=True,
            )
        )
    )
    mismatch_fields = {item["field"] for item in payload["mismatches"]}

    assert payload["classification"] == "runner_owned_boundary_mismatch", payload
    assert payload["clean"] is False, payload
    assert payload["mismatch_count"] == 4, payload
    assert "submit_eligible" in mismatch_fields, payload
    assert "leaderboard_evidence" in mismatch_fields, payload
    assert "read_boundary.raw_artifacts_read" in mismatch_fields, payload
    assert "read_boundary.task_text_read" in mismatch_fields, payload
    assert (
        payload["claim_boundary"]["worker_may_override_runner_owned_fields"]
        is False
    ), payload
    assert "boundary-mismatch" in payload["repair_recommendation"], payload


def test_cli_review_runner_invariants() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clean_path = root / "clean.compact.json"
        mismatch_path = root / "mismatch.compact.json"
        clean_path.write_text(json.dumps(benchmark_run()), encoding="utf-8")
        mismatch_path.write_text(
            json.dumps(
                benchmark_run(
                    submit_eligible=True,
                    leaderboard_evidence=True,
                    raw_artifacts_read=True,
                )
            ),
            encoding="utf-8",
        )

        clean = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "review-runner-invariants",
                "--benchmark-run-json",
                str(clean_path),
                "--require-clean",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        clean_payload = json.loads(clean.stdout)
        assert clean_payload["ok"] is True, clean_payload
        assert clean_payload["clean"] is True, clean_payload
        assert str(root) not in clean.stdout, clean.stdout
        assert "/tmp/private" not in clean.stdout, clean.stdout

        mismatch = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "review-runner-invariants",
                "--benchmark-run-json",
                str(mismatch_path),
                "--require-clean",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert mismatch.returncode == 1, mismatch.stdout
        mismatch_payload = json.loads(mismatch.stdout)
        assert mismatch_payload["ok"] is False, mismatch_payload
        assert (
            mismatch_payload["classification"] == "runner_owned_boundary_mismatch"
        ), mismatch_payload
        assert mismatch_payload["mismatch_count"] == 3, mismatch_payload
        assert str(root) not in mismatch.stdout, mismatch.stdout
        assert "/tmp/private" not in mismatch.stdout, mismatch.stdout


def main() -> int:
    test_clean_runner_owned_boundary()
    test_worker_cannot_widen_runner_owned_boundary()
    test_cli_review_runner_invariants()
    print("benchmark-runner-invariant-review-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
