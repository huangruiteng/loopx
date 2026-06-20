#!/usr/bin/env python3
"""Smoke-test generic Harbor job result reduction."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "harbor_job_result_reducer.py"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_fake_job(root: Path) -> Path:
    job = root / "jobs" / "swe-marathon-smoke-job"
    trial = job / "find-network-alignments__attempt-1"
    _write_json(
        job / "lock.json",
        {
            "invocation": ["harbor", "run", "-p", "<task-dir>", "--agent", "codex-api-key-no-search"],
            "trials": [
                {
                    "agent": {
                        "name": "codex-api-key-no-search",
                        "model_name": "gpt-5.5",
                        "kwargs": {},
                    },
                    "task": {"name": "find-network-alignments"},
                }
            ],
        },
    )
    _write_json(job / "config.json", {"job_name": job.name})
    _write_json(
        trial / "result.json",
        {
            "agent_result": {},
            "exception_info": {
                "exception_type": "NonZeroAgentExitCodeError",
            },
            "finished_at": _iso(),
            "started_at": _iso(),
            "task_name": "find-network-alignments",
            "trial_name": trial.name,
            "verifier_result": {"rewards": {"reward": 0.0}},
        },
    )
    _write_json(trial / "config.json", {"trial_name": trial.name})
    _write_json(
        job / "result.json",
        {
            "finished_at": _iso(),
            "n_total_trials": 1,
            "started_at": _iso(),
            "stats": {
                "evals": {
                    "codex-api-key-no-search__gpt-5.5__adhoc": {
                        "exception_stats": {
                            "NonZeroAgentExitCodeError": ["find-network-alignments"]
                        },
                        "metrics": [{"mean": 0.0}],
                        "n_errors": 1,
                        "n_trials": 0,
                    }
                },
                "n_cancelled_trials": 0,
                "n_completed_trials": 1,
                "n_errored_trials": 1,
                "n_pending_trials": 0,
                "n_retries": 0,
                "n_running_trials": 0,
            },
            "updated_at": _iso(),
        },
    )
    return job


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gh-harbor-reducer-") as tmp:
        job = _write_fake_job(Path(tmp))
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--job-dir",
                str(job),
                "--benchmark-id",
                "swe-marathon",
                "--pretty",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True, payload
        compact = payload["compact_benchmark_run"]
        assert compact["benchmark_id"] == "swe-marathon", compact
        assert compact["source_runner"] == "harbor", compact
        assert compact["progress"]["n_errored_trials"] == 1, compact
        assert compact["official_task_score"]["value"] == 0.0, compact
        assert compact["score_failure_attribution"] == (
            "agent_process_nonzero_exit_score_failure"
        )
        rendered = json.dumps(payload, sort_keys=True)
        assert str(tmp) not in rendered, rendered
        assert "<task-dir>" not in rendered, rendered

    print("harbor-job-result-reducer smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
