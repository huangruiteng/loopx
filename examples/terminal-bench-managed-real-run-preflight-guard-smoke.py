#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench managed real-run preflight guard."""

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


TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-managed-real-run-preflight-guard-v0.md"
README = TOPIC_DIR / "README.md"

GOAL_ID = "terminal-bench-managed-preflight-fixture"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_ID = "build-cython-ext"
RUN_MODE = "loopx_managed_codex_real_run_preflight_guard"
WORKER_MODE = "loopx_managed_codex_cli"

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench Managed Real-Run Preflight Guard V0",
    "loopx benchmark run terminal-bench",
    "--preflight-guard",
    "loopx_managed_codex_real_run_preflight_guard",
    "ready_for_private_managed_no_upload_pilot_review",
    "auth-surface variable names are checked",
    "credential values are never read or stored",
    "python3 examples/terminal-bench-managed-real-run-preflight-guard-smoke.py",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "ARK" + "_BASE_URL=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "fixture-preflight-value",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]


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
        "updated_at: 2026-06-08T00:00:00+00:00\n"
        "---\n\n"
        "# Terminal-Bench Managed Preflight Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Run the Terminal-Bench managed preflight guard.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-08T00:00:00+00:00",
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
                    "heartbeat": {
                        "enabled": True,
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


def run_cli(args: list[str], *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def run_cli_json(args: list[str], *, env: dict[str, str]) -> dict[str, Any]:
    result = run_cli(args, env=env)
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
        "loopx-managed-codex",
        "--dataset",
        BENCHMARK_ID,
        "--include-task-name",
        TASK_ID,
        "--preflight-guard",
        "--no-global-sync",
    ]


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 18000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "terminal-bench-managed-real-run-preflight-guard-v0.md" in readme, readme
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def assert_payload(payload: dict[str, Any], *, appended: bool) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    assert payload["dry_run"] is (not appended), payload
    assert payload["classification"] == "terminal_bench_managed_real_run_preflight_guard_v0", payload
    assert payload["benchmark_cli"]["benchmark"] == "terminal-bench", payload
    assert payload["benchmark_cli"]["mode"] == "loopx-managed-codex", payload
    assert payload["benchmark_cli"]["fake_worker"] is False, payload
    assert payload["benchmark_cli"]["preflight_guard"] is True, payload
    assert payload["benchmark_cli"]["real_runner_invoked"] is False, payload
    assert payload["benchmark_cli"]["real_codex_invoked"] is False, payload
    assert payload["benchmark_cli"]["auth_values_read"] is False, payload

    event = payload["benchmark_run"]
    assert event["schema_version"] == "benchmark_run_v0", event
    assert event["source_runner"] == "loopx_terminal_bench_managed_real_run_preflight_guard", event
    assert event["benchmark_id"] == BENCHMARK_ID, event
    assert event["mode"] == RUN_MODE, event
    assert event["worker_mode"] == WORKER_MODE, event
    assert event["first_blocker"] == "ready_for_private_managed_no_upload_pilot_review", event
    assert event["agent"]["model"] == "gpt-5.5", event
    assert event["progress"]["n_total_trials"] == 0, event
    assert event["metrics"]["cost_usd"] == 0, event
    assert event["trials"][0]["exception_type"] == "ready_for_private_managed_no_upload_pilot_review", event
    assert event["validation"]["all_passed"] is True, event
    assert event["validation"]["failed_checks"] == [], event
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert event["official_task_score"]["kind"] == "not_run", event
    assert event["loopx_inside_case"] is True, event
    assert event["official_score_comparable_to_native_codex"] is False, event
    assert event["model_plus_harness_pair"] is True, event
    assert event["leaderboard_evidence"] is False, event
    assert_public_safe(payload)


def assert_status_projection(registry_path: Path, runtime: Path) -> None:
    status = collect_status(
        registry_path=registry_path,
        runtime_root_override=str(runtime),
        scan_roots=[],
        limit=5,
    )
    assert status["ok"], status
    latest = status["run_history"]["goals"][0]["latest_runs"][0]
    summary = latest["benchmark_run_summary"]
    assert summary["mode"] == RUN_MODE, summary
    assert summary["first_blocker"] == "ready_for_private_managed_no_upload_pilot_review", summary
    assert summary["benchmark_id"] == BENCHMARK_ID, summary
    assert summary["progress"]["n_total_trials"] == 0, summary
    assert status["event_ledger_summary"]["totals"]["benchmark_runs_24h"] == 1, status
    assert_public_safe(summary)


def assert_hardened_control_preflight(registry_path: Path, runtime: Path, env: dict[str, str]) -> None:
    args = common_args(registry_path, runtime)
    mode_index = args.index("--mode") + 1
    args[mode_index] = "hardened-codex"
    payload = run_cli_json(args, env=env)
    assert payload["ok"] is True, payload
    assert payload["classification"] == "hardened_codex_baseline_preflight_guard_v0", payload
    assert payload["benchmark_cli"]["mode"] == "hardened-codex", payload
    event = payload["benchmark_run"]
    assert event["mode"] == "hardened_codex_baseline_preflight_guard", event
    assert event["worker_mode"] == "hardened_codex_baseline", event
    assert event["loopx_inside_case"] is False, event
    assert event["case_semantics_changed_by_harness"] is False, event
    assert event["hardened_install_baseline"] is True, event
    assert event["preflight_guard"]["schema_version"] == (
        "terminal_bench_hardened_codex_baseline_preflight_guard_v0"
    ), event
    assert_public_safe(payload)


def assert_guard_rejects_fake_worker(registry_path: Path, runtime: Path, env: dict[str, str]) -> None:
    result = run_cli(common_args(registry_path, runtime) + ["--fake-worker"], env=env, check=False)
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False, payload
    assert "cannot be combined" in payload["error"], payload


def main() -> None:
    assert_doc_contract()
    with tempfile.TemporaryDirectory(prefix="terminal-bench-managed-preflight-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_fixture(root)
        fake_bin = write_fake_surface_commands(root)
        env = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "CODEX_FORCE_AUTH_JSON": "fixture-preflight-value",
        }
        dry_payload = run_cli_json(common_args(registry_path, runtime), env=env)
        assert_payload(dry_payload, appended=False)

        execute_payload = run_cli_json(
            common_args(registry_path, runtime)
            + [
                "--delivery-batch-scale",
                "multi_surface",
                "--delivery-outcome",
                "outcome_progress",
                "--execute",
            ],
            env=env,
        )
        assert_payload(execute_payload, appended=True)
        assert_status_projection(registry_path, runtime)
        assert_hardened_control_preflight(registry_path, runtime, env)
        assert_guard_rejects_fake_worker(registry_path, runtime, env)

    print(
        "terminal-bench-managed-real-run-preflight-guard-smoke ok "
        f"mode={RUN_MODE} real_run=False"
    )


if __name__ == "__main__":
    main()
