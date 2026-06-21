#!/usr/bin/env python3
"""Smoke-test active-user assisted observation fixture projection."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import collect_status  # noqa: E402


GOAL_ID = "terminal-bench-active-user-observation-fixture"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_ID = "train-fasttext"
CLASSIFICATION = "terminal_bench_active_user_assisted_observation_fixture_v0"
RUN_MODE = "codex_loopx_active_user_assisted_observation_fixture"
FIRST_BLOCKER = "real_assisted_worker_observation_fixture_only_no_real_case"
OBSERVATION_SCHEMA = "loopx_active_user_intervention_observation_v0"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-10T00:00:00+00:00\n"
        "---\n\n"
        "# Terminal-Bench Active User Observation Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Prove worker after-start active-user observation.\n",
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
                    "domain": "loopx-platform",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                }
            ],
        },
    )
    return registry_path, runtime


def write_fake_command(bin_dir: Path, name: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_fake_surface_commands(root: Path) -> Path:
    bin_dir = root / "fake-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in ("uvx", "docker", "colima", "codex"):
        write_fake_command(bin_dir, name)
    return bin_dir


def run_cli_json(args: list[str], *, env: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def common_args(registry_path: Path, runtime: Path) -> list[str]:
    return [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "benchmark",
        "run",
        "terminal-bench",
        "--goal-id",
        GOAL_ID,
        "--mode",
        "codex-loopx",
        "--dataset",
        BENCHMARK_ID,
        "--include-task-name",
        TASK_ID,
        "--preflight-guard",
        "--active-cli-bridge",
        "--active-user-assisted-treatment",
        "--active-user-observation-fixture",
        "--no-global-sync",
    ]


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
    assert len(text) < 30000, len(text)


def assert_observation(observation: dict[str, Any]) -> None:
    assert observation["schema_version"] == OBSERVATION_SCHEMA, observation
    assert observation["feed_present"] is True, observation
    assert observation["feed_path_recorded"] is False, observation
    assert observation["worker_start_seq"] == 1, observation
    assert observation["valid_intervention_count"] == 2, observation
    assert observation["observed_after_worker_start"] is True, observation
    assert observation["observed_intervention_count"] == 1, observation
    assert observation["worker_observation_proof"] is True, observation
    latest = observation["latest_intervention"]
    assert latest["seq"] == 2, observation
    assert latest["message"] == "Run the focused public validation before broader edits.", observation
    assert latest["oracle_free"] is True, observation
    assert latest["hidden_tests_visible"] is False, observation
    assert latest["expected_solution_visible"] is False, observation
    boundary = observation["claim_boundary"]
    assert boundary["assisted_collaboration_claim_allowed"] is True, observation
    assert boundary["official_score_claim_allowed"] is False, observation
    assert boundary["leaderboard_claim_allowed"] is False, observation


def assert_benchmark_run(run: dict[str, Any], *, appended: bool) -> None:
    assert run["schema_version"] == "benchmark_run_v0", run
    assert run["benchmark_id"] == BENCHMARK_ID, run
    assert run["mode"] == RUN_MODE, run
    assert run["worker_mode"] == "codex_loopx_cli", run
    assert run["first_blocker"] == FIRST_BLOCKER, run
    assert run["real_run"] is False, run
    assert run["submit_eligible"] is False, run
    assert run["leaderboard_evidence"] is False, run
    assert run["official_task_score"]["kind"] == "not_run", run
    assert run["assisted_collaboration_claim_allowed"] is True, run
    assert run["official_score_claim_allowed"] is False, run
    assert run["active_user_simulator_injection_channel_available"] is True, run
    assert run["worker_loopx_cli_call_total"] == 1, run
    assert run["loopx_counter_scope"] == "worker_active_user_observation_fixture", run
    counters = run["interaction_counters"]
    assert counters["loopx_cli_calls"]["active_user_observe"] == 1, counters
    assert counters["loopx_cli_calls"]["total"] == 1, counters
    assert counters["loopx_state_reads"] == 1, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "worker_active_user_observe_fixture_no_official_run", counters
    assert counters["counter_trust_level"] == "active_user_observation_fixture_audited", counters
    validation = run["validation"]
    assert validation["active_user_assisted_treatment_preflight"] is True, validation
    assert validation["active_user_observation_fixture"] is True, validation
    assert validation["worker_observation_proof"] is True, validation
    assert validation["scripted_active_user_intervention_observed"] is True, validation
    assert "real_assisted_worker_observation_missing" not in validation, validation
    assert_observation(run["active_user_observation"])
    assert_public_safe(run)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="terminal-bench-active-user-observation-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_fixture(root)
        fake_bin = write_fake_surface_commands(root)
        env = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "CODEX_FORCE_AUTH_JSON": "true",
        }

        dry_payload = run_cli_json(common_args(registry_path, runtime), env=env)
        assert dry_payload["ok"] is True, dry_payload
        assert dry_payload["appended"] is False, dry_payload
        assert dry_payload["classification"] == CLASSIFICATION, dry_payload
        assert_benchmark_run(dry_payload["benchmark_run"], appended=False)

        execute_payload = run_cli_json(
            common_args(registry_path, runtime)
            + [
                "--delivery-batch-scale",
                "single_surface",
                "--delivery-outcome",
                "outcome_progress",
                "--execute",
            ],
            env=env,
        )
        assert execute_payload["ok"] is True, execute_payload
        assert execute_payload["appended"] is True, execute_payload
        assert execute_payload["classification"] == CLASSIFICATION, execute_payload
        assert_benchmark_run(execute_payload["benchmark_run"], appended=True)

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=5,
        )
        assert status["ok"], status
        latest = status["run_history"]["goals"][0]["latest_runs"][0]
        summary = latest["benchmark_run_summary"]
        assert_benchmark_run(summary, appended=True)

    print(
        "terminal-bench-active-user-assisted-observation-fixture-smoke ok "
        f"mode={RUN_MODE} proof=true"
    )


if __name__ == "__main__":
    main()
