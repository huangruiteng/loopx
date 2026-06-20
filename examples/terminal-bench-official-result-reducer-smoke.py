#!/usr/bin/env python3
"""Smoke-test the official Terminal-Bench compact result reducer."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "terminal_bench_official_result_reducer.py"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        results = root / "results.json"
        metadata = root / "run_metadata.json"
        write_json(
            results,
            {
                "accuracy": 1.0,
                "id": "sample-run",
                "n_resolved": 1,
                "n_unresolved": 0,
                "resolved_ids": ["hello-world"],
                "results": [
                    {
                        "instruction": "raw trial task text must not appear",
                        "is_resolved": True,
                        "failure_mode": "none",
                        "parser_results": {"raw": "verifier detail"},
                        "recording_path": "/private/raw/recording.cast",
                        "task_id": "hello-world",
                        "total_input_tokens": 12,
                        "total_output_tokens": 3,
                    }
                ],
                "unresolved_ids": [],
            },
        )
        write_json(
            metadata,
            {
                "accuracy": 1.0,
                "agent_name": "oracle",
                "cleanup": True,
                "dataset_path": "/private/raw/tasks",
                "dataset_size": 1,
                "end_time": "2026-06-19T16:29:09+00:00",
                "model_name": "Oracle",
                "n_attempts": 1,
                "n_concurrent_trials": 1,
                "no_rebuild": True,
                "output_path": "/private/raw/runs",
                "run_id": "sample-run",
                "start_time": "2026-06-19T16:28:48+00:00",
                "task_ids": ["hello-world"],
            },
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--results-json",
                str(results),
                "--run-metadata-json",
                str(metadata),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True, payload
        assert payload["accuracy"] == 1.0, payload
        assert payload["n_resolved"] == 1, payload
        assert payload["n_unresolved"] == 0, payload
        assert payload["trial_summary"]["failure_modes"] == {"none": 1}, payload
        assert payload["trial_summary"]["resolved_trial_count"] == 1, payload
        assert payload["trial_summary"]["token_totals"] == {
            "input": 12,
            "output": 3,
        }, payload
        assert payload["compact_benchmark_run"]["schema_version"] == "benchmark_run_v0"
        assert payload["compact_benchmark_run"]["benchmark_id"] == "terminal-bench@2.0"
        assert payload["compact_benchmark_run"]["case_id"] == "hello-world"
        assert payload["compact_benchmark_run"]["official_score_status"] == "completed"
        assert payload["compact_benchmark_run"]["official_score"] == 1.0
        assert payload["compact_benchmark_run"]["trials"][0]["task_id"] == "hello-world"
        assert payload["task_ids"] == ["hello-world"], payload
        assert payload["boundary"]["raw_task_text_read"] is False, payload
        assert payload["boundary"]["private_paths_recorded"] is False, payload
        rendered = json.dumps(payload, sort_keys=True)
        assert "/private/raw" not in rendered, rendered
        assert "raw trial task text" not in rendered, rendered
        assert (
            payload["source_contract"]["trial_level_results_json"]
            == "safe_whitelisted_fields_only"
        )

        unsafe = root / "trial-results.json"
        write_json(
            unsafe,
            {
                "instruction": "do not echo this raw task text",
                "is_resolved": True,
                "task_id": "hello-world",
            },
        )
        rejected = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--results-json",
                str(unsafe),
                "--run-metadata-json",
                str(metadata),
                "--metadata-only",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert rejected.returncode == 0, rejected
        metadata_only = json.loads(rejected.stdout)
        assert metadata_only["ok"] is True, metadata_only
        assert metadata_only["evidence_kind"] == "official_run_metadata_only"
        assert metadata_only["compact_benchmark_run"]["case_id"] == "hello-world"
        assert metadata_only["compact_benchmark_run"]["official_score"] == 1.0
        assert metadata_only["source_contract"]["results_json"] == "not_read_metadata_only"

        rejected = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--results-json",
                str(unsafe),
                "--run-metadata-json",
                str(metadata),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert rejected.returncode == 2, rejected
        rejection = json.loads(rejected.stdout)
        assert rejection["ok"] is False, rejection
        assert rejection["forbidden_keys"] == ["instruction"], rejection
        assert "do not echo" not in rejected.stdout, rejected.stdout

    print("terminal-bench-official-result-reducer-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
