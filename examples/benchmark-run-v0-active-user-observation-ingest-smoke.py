#!/usr/bin/env python3
"""Smoke-test ingesting active-user observation through benchmark_run_v0."""

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

from loopx.status import collect_status  # noqa: E402
from loopx.worker_bridge import (  # noqa: E402
    build_active_user_intervention,
    observe_active_user_intervention_feed,
    write_active_user_observation_file,
)


GOAL_ID = "active-user-observation-ingest-fixture"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        ".local/" + "benchmark-runs",
        "OPENAI" + "_API_KEY",
        "ARK" + "_API_KEY",
        "CODEX" + "_AUTH_JSON_PATH",
        "auth.json",
        "raw" + "_thread",
        "session" + "_history",
        "sk-" + "example",
        "tok" + "en=",
        "-----BEGIN",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked
    assert len(text) < 18000, len(text)


def build_observation(root: Path) -> dict[str, Any]:
    feed = root / "feed.jsonl"
    observation_path = root / "observation.json"
    append_jsonl(
        feed,
        build_active_user_intervention(
            seq=1,
            message="Record worker start before assisted observation.",
            created_after_worker_start=False,
        ),
    )
    append_jsonl(
        feed,
        build_active_user_intervention(
            seq=2,
            message="Run the focused public validation before wider edits.",
            created_after_worker_start=True,
        ),
    )
    observation = observe_active_user_intervention_feed(feed, worker_start_seq=1)
    assert observation["observed_after_worker_start"] is True, observation
    assert observation["feed_path_recorded"] is False, observation
    assert write_active_user_observation_file(observation_path, observation)
    assert_public_safe(observation)
    return observation


def build_benchmark_run(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "active_user_observation_ingest_smoke",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "active_user_observation_ingest_fixture",
        "mode": "codex_loopx_active_user_assisted_observation_fixture",
        "worker_mode": "codex_loopx_cli",
        "real_run": False,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "assisted_collaboration_claim_allowed": True,
        "official_score_claim_allowed": False,
        "active_user_simulator_injection_channel_available": True,
        "official_task_score": {
            "kind": "not_run",
            "value": None,
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 1,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
        },
        "validation": {
            "active_user_observation_ingested": True,
            "worker_observation_proof": True,
            "assisted_score_kept_separate_from_official": True,
            "no_leaderboard_upload_requested": True,
            "paths_redacted": True,
        },
        "active_user_observation": observation,
        "trials": [
            {
                "task_id": "active-user-observation-fixture",
                "trial_name": "active-user-observation-fixture-worker",
                "source": "terminal-bench@2.0",
                "reward": {"reward": 0},
                "trajectory_present": False,
                "verifier_reward_present": False,
                "artifact_manifest_present": False,
                "trial_result_present": False,
            }
        ],
        "evidence_files": [
            "worker:loopx-active-user-observation.json",
            "smoke:benchmark-run-v0-active-user-observation-ingest-smoke.py",
        ],
        "stop_conditions": [
            "do_not_run_terminal_bench",
            "do_not_upload_or_submit_leaderboard",
            "do_not_claim_official_score_from_assisted_observation",
        ],
    }


def write_fixture(root: Path, benchmark_run: dict[str, Any]) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    registry_path = project / ".loopx" / "registry.json"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    benchmark_run_path = project / "benchmark-run.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-10T00:00:00+00:00\n"
        "---\n\n"
        "# Active User Observation Ingest Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Ingest active-user observation through benchmark_run_v0.\n\n"
        "## Next Action\n\n"
        "- Inspect compact active_user_observation in benchmark_run status.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-10T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-projection",
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
    write_json(benchmark_run_path, benchmark_run)
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


def assert_summary(summary: dict[str, Any]) -> None:
    assert summary["schema_version"] == "benchmark_run_v0", summary
    assert summary["real_run"] is False, summary
    assert summary["submit_eligible"] is False, summary
    assert summary["leaderboard_evidence"] is False, summary
    assert summary["assisted_collaboration_claim_allowed"] is True, summary
    assert summary["official_score_claim_allowed"] is False, summary
    assert summary["official_task_score"]["kind"] == "not_run", summary
    observation = summary["active_user_observation"]
    assert observation["worker_observation_proof"] is True, observation
    assert observation["observed_after_worker_start"] is True, observation
    assert observation["feed_path_recorded"] is False, observation
    assert observation["worker_start_seq"] == 1, observation
    assert observation["observed_intervention_count"] == 1, observation
    assert observation["latest_intervention"]["seq"] == 2, observation
    assert observation["latest_intervention"]["oracle_free"] is True, observation
    assert observation["latest_intervention"]["hidden_tests_visible"] is False, observation
    assert observation["claim_boundary"]["official_score_claim_allowed"] is False, observation
    assert observation["claim_boundary"]["leaderboard_claim_allowed"] is False, observation
    assert observation["claim_boundary"]["assisted_collaboration_claim_allowed"] is True, observation
    assert observation["public_boundary"]["raw_paths_recorded"] is False, observation
    assert_public_safe(summary)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-active-user-observation-") as tmp:
        root = Path(tmp)
        observation = build_observation(root)
        benchmark_run = build_benchmark_run(observation)
        registry_path, runtime, benchmark_run_path = write_fixture(root, benchmark_run)
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
        assert dry_run["benchmark_run"]["active_user_observation"]["worker_observation_proof"] is True, dry_run
        assert not index_path.exists(), index_path

        appended = run_cli([*base_args, "--execute"])
        assert appended["ok"], appended
        assert appended["appended"] is True, appended
        assert_public_safe(appended["benchmark_run"])

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        latest_runs = status["run_history"]["goals"][0]["latest_runs"]
        run = next(run for run in latest_runs if run.get("classification") == "benchmark_run_v0")
        assert_summary(run["benchmark_run_summary"])

    print("benchmark-run-v0-active-user-observation-ingest-smoke ok proof=true")


if __name__ == "__main__":
    main()
