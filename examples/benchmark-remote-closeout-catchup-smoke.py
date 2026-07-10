#!/usr/bin/env python3
"""Smoke-test generic remote benchmark ledger catch-up closeout."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core.remote_closeout import closeout_remote_benchmark_batch


def _compact(case_id: str, score: float) -> dict[str, object]:
    return {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "skillsbench@1.1",
        "case_id": case_id,
        "route": "codex-cli-goal-baseline",
        "status": "completed",
        "official_score": score,
    }


def _write_compact(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _collection(payload: dict[str, object]) -> str:
    content = (json.dumps(payload) + "\n").encode("utf-8")
    return json.dumps(
        {
            "artifacts": [
                {
                    "relative_path": "current/benchmark_run.compact.json",
                    "content_base64": base64.b64encode(content).decode("ascii"),
                }
            ],
            "matched_count": 1,
            "blocked_count": 0,
        }
    )


def test_closeout_catches_up_public_target_rows_once() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-closeout-catchup-") as tmp:
        root = Path(tmp)
        catchup_root = root / "public-runs"
        accepted = catchup_root / "target-old" / "benchmark_run.compact.json"
        ignored = catchup_root / "other-lane" / "benchmark_run.compact.json"
        private = catchup_root / "target-old" / "logs" / "benchmark_run.compact.json"
        malformed = catchup_root / "target-malformed" / "benchmark_run.compact.json"
        _write_compact(accepted, _compact("case-b", 1.0))
        _write_compact(ignored, _compact("case-c", 1.0))
        _write_compact(private, _compact("private-case", 1.0))
        malformed.parent.mkdir(parents=True)
        malformed.write_text("{not-json\n", encoding="utf-8")

        canonical = root / "canonical.txt"
        canonical.write_text("case-a\ncase-b\n", encoding="utf-8")
        ledger = root / "ledger.json"
        aggregate = root / "aggregate.json"
        collection = _collection(_compact("case-a", 0.0))

        def run_closeout() -> dict[str, object]:
            return closeout_remote_benchmark_batch(
                run_remote_command=lambda _command, _timeout: subprocess.CompletedProcess(
                    [], 0, collection, ""
                ),
                remote_root="/redacted",
                artifact_globs=["current/benchmark_run.compact.json"],
                local_public_artifact_dir=root / "current",
                adapter_kind="skillsbench",
                max_bytes=1024 * 1024,
                sync_timeout_sec=1,
                ledger_path=str(ledger),
                run_group_id="target-current",
                aggregate_path=str(aggregate),
                canonical_case_ids_file=str(canonical),
                benchmark_id="skillsbench@1.1",
                target_run_group_contains=["target-"],
                ledger_catchup_root=str(catchup_root),
                ledger_catchup_run_group_contains=["target-"],
                repo_root=REPO_ROOT,
            )

        first = run_closeout()
        update = first["local_ledger_update"]
        assert first["ok"] is True, first
        assert update["upserted_count"] == 2, update
        assert update["catchup_compact_count"] == 2, update
        assert update["catchup_upserted_count"] == 1, update
        assert update["catchup_skipped_count"] == 1, update
        assert update["catchup_blocked_count"] == 1, update
        cases = json.loads(ledger.read_text(encoding="utf-8"))["benchmarks"][
            "skillsbench@1.1"
        ]["cases"]
        assert set(cases) == {"case-a", "case-b"}, cases
        assert json.loads(aggregate.read_text(encoding="utf-8"))["canonical_total"] == 2

        second = run_closeout()
        retry = second["local_ledger_update"]
        assert retry["catchup_upserted_count"] == 0, retry
        assert retry["catchup_already_present_count"] == 1, retry
        cases = json.loads(ledger.read_text(encoding="utf-8"))["benchmarks"][
            "skillsbench@1.1"
        ]["cases"]
        assert len(cases["case-b"]["runs"]) == 1, cases["case-b"]


def test_closeout_rejects_missing_catchup_root() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-closeout-catchup-missing-") as tmp:
        root = Path(tmp)
        result = closeout_remote_benchmark_batch(
            run_remote_command=lambda _command, _timeout: subprocess.CompletedProcess(
                [], 0, _collection(_compact("case-a", 0.0)), ""
            ),
            remote_root="/redacted",
            artifact_globs=["current/benchmark_run.compact.json"],
            local_public_artifact_dir=root / "current",
            adapter_kind="skillsbench",
            max_bytes=1024 * 1024,
            sync_timeout_sec=1,
            ledger_path=str(root / "ledger.json"),
            run_group_id="target-current",
            ledger_catchup_root=str(root / "missing"),
            ledger_catchup_run_group_contains=["target-"],
            repo_root=REPO_ROOT,
        )
        assert result["ok"] is False, result
        assert result["first_blocker"] == "public_artifact_local_closeout_failed", result
        assert result["local_closeout_error_type"] == "ValueError", result
        assert not (root / "ledger.json").exists(), result


if __name__ == "__main__":
    test_closeout_catches_up_public_target_rows_once()
    test_closeout_rejects_missing_catchup_root()
    print("benchmark-remote-closeout-catchup-smoke: ok")
