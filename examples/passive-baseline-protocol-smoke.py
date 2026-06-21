#!/usr/bin/env python3
"""Smoke-test the passive baseline protocol through benchmark_run_v0 appends."""

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


TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
PROTOCOL = TOPIC_DIR / "passive-baseline-protocol-v0.md"
GOAL_ID = "passive-baseline-fixture"
TASK_ID = "mini_control_plane_repair_v0"
BENCHMARK_ID = "loopx-local-passive-baseline@v0"
BASELINE_MODE = "codex_goal_mode_baseline"
TREATMENT_MODE = "passive_loopx_wrapper"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def benchmark_run_event(mode: str, *, control_value: float, spend_count: int) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "loopx-local-fixture",
        "benchmark_id": BENCHMARK_ID,
        "job_name": f"{TASK_ID}__{mode}",
        "mode": mode,
        "agent": {
            "name": "codex-cli-fixture",
            "model": "deterministic-shim",
            "kwargs_keys": ["no_operator_simulator"],
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        },
        "trials": [
            {
                "task_id": TASK_ID,
                "trial_name": f"{TASK_ID}__{mode}__attempt-1",
                "source": BENCHMARK_ID,
                "reward": {"reward": 1.0, "control_plane_score": control_value},
                "metrics": {
                    "input_tokens": 0,
                    "cache_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                },
                "trajectory_present": mode == TREATMENT_MODE,
                "verifier_reward_present": True,
                "artifact_manifest_present": True,
                "trial_result_present": True,
            }
        ],
        "validation": {
            "same_task_pair": True,
            "no_operator_simulator": True,
            "official_task_score_delta_zero": True,
            "control_plane_score_recorded": True,
            "codex_goal_mode_enabled": True,
            "spend_after_validation_only": spend_count > 0 or mode == BASELINE_MODE,
            "no_leaderboard_upload_requested": True,
            "paths_redacted": True,
        },
        "evidence_files": [
            "fixture:benchmark_result_v0",
            "fixture:benchmark_comparison_v0",
            "fixture:public_artifact_manifest",
        ],
        "resume_or_inspect_commands": [
            "python3 examples/codex-cli-long-run-benchmark-smoke.py",
            "loopx history --goal-id <goal-id> --limit 2",
        ],
        "stop_conditions": [
            "do_not_invoke_real_benchmark_or_model_api_from_heartbeat",
            "do_not_use_operator_simulator_in_passive_baseline",
            "do_not_claim_official_leaderboard_improvement_from_local_fixture",
        ],
    }


def write_fixture(root: Path) -> tuple[Path, Path, dict[str, Path]]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    event_paths = {
        BASELINE_MODE: root / f"{BASELINE_MODE}.benchmark_run.json",
        TREATMENT_MODE: root / f"{TREATMENT_MODE}.benchmark_run.json",
    }

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-07T00:00:00+00:00\n"
        "---\n\n"
        "# Passive Baseline Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Append Codex goal-mode baseline and passive-wrapper benchmark_run_v0 rows.\n\n"
        "## Next Action\n\n"
        "- Inspect the paired passive baseline benchmark rows.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-07T00:00:00+00:00",
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
    write_json(
        event_paths[BASELINE_MODE],
        benchmark_run_event(BASELINE_MODE, control_value=0.70, spend_count=0),
    )
    write_json(
        event_paths[TREATMENT_MODE],
        benchmark_run_event(TREATMENT_MODE, control_value=0.86, spend_count=3),
    )
    return registry_path, runtime, event_paths


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


def append_event(registry_path: Path, runtime: Path, mode: str, event_path: Path) -> dict[str, Any]:
    return run_cli(
        [
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
            str(event_path),
            "--recommended-action",
            "inspect passive baseline pair and continue only after both modes are present",
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "primary_goal_outcome",
            "--execute",
            "--no-global-sync",
        ]
    )


def assert_no_private_surface(summary: dict[str, Any]) -> None:
    text = json.dumps(summary, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        "OPENAI_API_KEY",
        "auth.json",
        "sessions/",
        "lark" + "office",
        "fei" + "shu.cn",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def assert_doc_contract() -> None:
    readme = README.read_text(encoding="utf-8")
    doc = PROTOCOL.read_text(encoding="utf-8")
    compact_doc = " ".join(doc.split())
    required = [
        "Passive Baseline Protocol V0",
        "`codex_goal_mode_baseline`",
        "`passive_loopx_wrapper`",
        "`codex_goal_mode_enabled`",
        "no simulated operator intervention is allowed",
        "`benchmark_result_v0`",
        "`benchmark_comparison_v0`",
        "append-benchmark-run",
        "official-task scores equal",
        "`control_plane_score` delta",
        "Do not claim official leaderboard improvement",
        "python3 examples/passive-baseline-protocol-smoke.py",
        "python3 examples/codex-cli-long-run-benchmark-smoke.py",
    ]
    missing = [snippet for snippet in required if snippet not in compact_doc]
    assert not missing, missing
    assert "passive-baseline-protocol-v0.md" in readme, readme


def main() -> None:
    assert_doc_contract()
    with tempfile.TemporaryDirectory(prefix="passive-baseline-protocol-") as tmp:
        registry_path, runtime, event_paths = write_fixture(Path(tmp))
        appended = [
            append_event(registry_path, runtime, mode, path)
            for mode, path in event_paths.items()
        ]
        assert all(item["ok"] and item["appended"] for item in appended), appended
        assert {item["benchmark_run"]["mode"] for item in appended} == {
            BASELINE_MODE,
            TREATMENT_MODE,
        }, appended

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        goal = status["run_history"]["goals"][0]
        summaries = [
            run.get("benchmark_run_summary")
            for run in goal["latest_runs"]
            if isinstance(run.get("benchmark_run_summary"), dict)
        ]
        modes = {summary["mode"] for summary in summaries}
        assert modes == {BASELINE_MODE, TREATMENT_MODE}, summaries
        assert status["event_ledger_summary"]["totals"]["benchmark_runs_24h"] == 2, status
        for summary in summaries:
            assert summary["benchmark_id"] == BENCHMARK_ID, summary
            assert summary["progress"]["n_completed_trials"] == 1, summary
            assert summary["validation"]["all_passed"] is True, summary
            assert summary["trials"][0]["reward"]["reward"] == 1.0, summary
            assert_no_private_surface(summary)

    print("passive-baseline-protocol-smoke ok")


if __name__ == "__main__":
    main()
