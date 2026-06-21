#!/usr/bin/env python3
"""Smoke-test posthoc Codex App parity checks for compact benchmark runs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core import (  # noqa: E402
    CODEX_APP_PARITY_POSTHOC_CHECK_SCHEMA_VERSION,
    build_codex_app_parity_posthoc_check,
)


def full_product_run() -> dict[str, object]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "fixture",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": "parity-posthoc-fixture",
        "mode": "codex_loopx",
        "route": "codex-loopx",
        "agent": {"name": "codex", "model": "fixture"},
        "progress": {},
        "metrics": {},
        "interaction_counters": {
            "schema_version": "fixture_interaction_counters_v0",
            "product_mode": True,
            "case_goal_state_init_required": True,
            "case_goal_state_initialized_before_agent": True,
            "case_goal_state_path": "/app/.codex/goals/terminal-bench-case/ACTIVE_GOAL_STATE.md",
            "loopx_cli_calls": {
                "status": 1,
                "quota_should_run": 1,
                "todo_list": 1,
                "history": 1,
                "check": 1,
                "total": 5,
            },
            "private_trajectory_summary_present": True,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
            "reward_feedback_forwarded": False,
        },
        "episode_policy": {"product_mode": True, "reward_feedback_forwarded": False},
        "trials": [],
        "evidence_files": [],
        "resume_or_inspect_commands": [],
        "real_run": False,
        "submit_eligible": False,
        "leaderboard_evidence": False,
    }


def surrogate_run() -> dict[str, object]:
    run = full_product_run()
    interaction = dict(run["interaction_counters"])  # type: ignore[index]
    interaction.update(
        {
            "case_goal_state_initialized_before_agent": False,
            "case_goal_state_path": "",
            "loopx_cli_calls": {"total": 0},
            "private_trajectory_summary_present": False,
        }
    )
    run["interaction_counters"] = interaction
    return run


def leaky_run() -> dict[str, object]:
    run = full_product_run()
    interaction = dict(run["interaction_counters"])  # type: ignore[index]
    interaction["reward_feedback_forwarded"] = True
    run["interaction_counters"] = interaction
    return run


def assert_direct_checks() -> None:
    good = build_codex_app_parity_posthoc_check(full_product_run())
    assert good["schema_version"] == CODEX_APP_PARITY_POSTHOC_CHECK_SCHEMA_VERSION
    assert good["full_product_claim_allowed"] is True, good
    assert good["missing_evidence"] == [], good
    assert good["safety_failures"] == [], good

    surrogate = build_codex_app_parity_posthoc_check(surrogate_run())
    assert surrogate["full_product_claim_allowed"] is False, surrogate
    assert surrogate["claim_level"] == "product_mode_surrogate_missing_posthoc_evidence"
    assert "canonical_case_active_state_path" in surrogate["missing_evidence"]
    assert "loopx_cli_trace_present" in surrogate["missing_evidence"]
    assert "codex_cli_trajectory_summary_present" in surrogate["missing_evidence"]

    leaky = build_codex_app_parity_posthoc_check(leaky_run())
    assert leaky["full_product_claim_allowed"] is False, leaky
    assert leaky["claim_level"] == "unsafe_or_leaky_artifact", leaky
    assert "raw_reward_feedback_absent" in leaky["safety_failures"], leaky


def assert_cli_check() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-parity-posthoc-") as raw_root:
        path = Path(raw_root) / "benchmark-run.json"
        path.write_text(
            json.dumps(full_product_run(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "parity-check",
                "--benchmark-run-json",
                str(path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        payload = json.loads(completed.stdout)
        assert payload["ok"] is True, payload
        check = payload["codex_app_parity_posthoc_check"]
        assert check["full_product_claim_allowed"] is True, check
        rendered = json.dumps(payload, sort_keys=True)
        assert "/Users/" not in rendered
        assert "raw_task_text_read" in rendered


def main() -> None:
    assert_direct_checks()
    assert_cli_check()


if __name__ == "__main__":
    main()

