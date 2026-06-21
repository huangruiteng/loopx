#!/usr/bin/env python3
"""Smoke-test ingesting a worker-written worker_bridge benchmark_run_v0."""

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

from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import collect_status  # noqa: E402
from loopx.worker_bridge import (  # noqa: E402
    build_worker_bridge_benchmark_run_from_counters,
    write_worker_bridge_benchmark_run_file,
)


GOAL_ID = "worker-bridge-ingest-fixture"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    registry_path = project / ".loopx" / "registry.json"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    benchmark_run_path = project / "worker-benchmark-run.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-09T00:00:00+00:00\n"
        "---\n\n"
        "# Worker Bridge Ingest Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Ingest a worker-written benchmark_run_v0 payload.\n\n"
        "## Next Action\n\n"
        "- Verify worker bridge ingest through normal history/status projection.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-09T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "worker-bridge-ingest",
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
    worker_payload = build_worker_bridge_benchmark_run_from_counters(
        {"loopx_cli_calls": {"total": 5}},
        counter_trace_present=True,
        source_runner="worker_bridge_ingest_smoke",
        benchmark_id="worker-bridge-ingest-smoke@v0",
        job_name="worker_bridge_ingest_smoke",
        task_id="worker-bridge-ingest-smoke",
        trial_name="worker-bridge-ingest-smoke-worker",
    )
    assert write_worker_bridge_benchmark_run_file(benchmark_run_path, worker_payload)
    return registry_path, runtime, benchmark_run_path


def run_cli(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        ".local/benchmark-runs",
        "OPENAI" + "_API_KEY",
        "ARK" + "_API_KEY",
        "CODEX" + "_AUTH_JSON_PATH",
        "auth.json",
        "raw" + "_thread",
        "session" + "_history",
        "lark" + "office",
        "fei" + "shu.cn",
        "sk-" + "example",
        "tok" + "en=",
        "-----BEGIN",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked
    assert len(text) < 16000, len(text)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="worker-bridge-ingest-") as tmp:
        registry_path, runtime, benchmark_run_path = write_fixture(Path(tmp))
        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
        base_args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-benchmark-run",
            "--goal-id",
            GOAL_ID,
            "--benchmark-run-json",
            str(benchmark_run_path),
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "outcome_progress",
            "--no-global-sync",
        ]

        dry_run = run_cli(base_args)
        assert dry_run["ok"], dry_run
        assert dry_run["dry_run"] is True, dry_run
        assert dry_run["appended"] is False, dry_run
        assert not index_path.exists(), index_path
        assert_public_safe(dry_run["benchmark_run"])

        appended = run_cli([*base_args, "--execute"])
        assert appended["ok"], appended
        assert appended["dry_run"] is False, appended
        assert appended["appended"] is True, appended
        assert index_path.exists(), index_path
        assert_public_safe(appended["benchmark_run"])

        index_records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(index_records) == 1, index_records
        assert index_records[0]["classification"] == "benchmark_run_v0", index_records
        assert index_records[0]["benchmark_run"]["schema_version"] == "benchmark_run_v0", index_records

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        latest_runs = status["run_history"]["goals"][0]["latest_runs"]
        run = next(run for run in latest_runs if run.get("classification") == "benchmark_run_v0")
        summary = run["benchmark_run_summary"]
        assert summary["schema_version"] == "benchmark_run_v0", summary
        assert summary["source_runner"] == "worker_bridge_ingest_smoke", summary
        assert summary["benchmark_id"] == "worker-bridge-ingest-smoke@v0", summary
        assert summary["worker_loopx_cli_call_total"] == 5, summary
        assert summary["loopx_worker_cli_bridge_trace_observed"] is True, summary
        assert summary["validation"]["all_passed"] is True, summary
        outcome = summary["worker_bridge_outcome"]
        assert outcome["worker_bridge_verified"] is True, summary
        assert outcome["runner_return_status"] == "pending_after_worker_bridge_success", summary
        assert outcome["official_score_status"] == "blocked_pending_runner_return", summary
        health = run["worker_bridge_ingest_health_note"]
        assert health["schema_version"] == "worker_bridge_ingest_health_note_v0", health
        assert health["health_state"] == "worker_bridge_verified_pending_runner_return", health
        assert health["evidence_layer"] == "worker_bridge_ingest_only", health
        assert health["worker_loopx_cli_call_total"] == 5, health
        assert health["runner_return_status"] == "pending_after_worker_bridge_success", health
        assert health["official_score_status"] == "blocked_pending_runner_return", health
        assert "raw trace public" in health["must_not_claim"], health
        assert_public_safe(summary)
        assert_public_safe(health)

        packet = build_review_packet(status, goal_id=GOAL_ID)
        assert packet["ok"], packet
        assert (
            "worker_bridge_health=worker_bridge_verified_pending_runner_return"
            in packet["project_agent_handoff"]
        ), packet["project_agent_handoff"]
        assert_public_safe({"project_agent_handoff": packet["project_agent_handoff"]})

    print("worker-bridge-benchmark-run-ingest-smoke ok worker_cli_calls=5")


if __name__ == "__main__":
    main()
