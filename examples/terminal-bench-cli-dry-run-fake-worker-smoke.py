#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench CLI dry-run/fake-worker skeleton."""

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
DOC = TOPIC_DIR / "terminal-bench-cli-dry-run-fake-worker-v0.md"
README = TOPIC_DIR / "README.md"

GOAL_ID = "terminal-bench-cli-dry-run-fixture"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_ID = "build-cython-ext"
RUN_MODE = "loopx_managed_codex_fake_worker_wrapper"
WORKER_MODE = "loopx_managed_codex_cli"

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench CLI Dry-Run Fake Worker V0",
    "loopx benchmark run terminal-bench",
    "codex_goal_mode_baseline_cli_dry_run",
    "--fake-worker",
    "benchmark_run_v0",
    "fixture-only",
    "loopx_managed_codex_fake_worker_wrapper",
    "fake_managed_worker_only_no_real_case",
    "official_score_comparable_to_native_codex=false",
    "python3 examples/terminal-bench-cli-dry-run-fake-worker-smoke.py",
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
        "# Terminal-Bench CLI Dry-Run Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Run the Terminal-Bench CLI dry-run/fake-worker skeleton.\n",
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


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_cli_json(args: list[str]) -> dict[str, Any]:
    result = run_cli(args)
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
        "--fake-worker",
        "--no-global-sync",
    ]


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 18000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    compact = " ".join(text.split())
    readme = README.read_text(encoding="utf-8")
    missing = [
        snippet
        for snippet in REQUIRED_DOC_SNIPPETS
        if snippet not in text and snippet not in compact
    ]
    assert not missing, missing
    assert "terminal-bench-cli-dry-run-fake-worker-v0.md" in readme, readme
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def assert_payload(payload: dict[str, Any], *, appended: bool) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    assert payload["dry_run"] is (not appended), payload
    assert payload["classification"] == "terminal_bench_cli_fake_worker_v0", payload
    assert payload["benchmark_cli"]["benchmark"] == "terminal-bench", payload
    assert payload["benchmark_cli"]["mode"] == "loopx-managed-codex", payload
    assert payload["benchmark_cli"]["fake_worker"] is True, payload
    assert payload["benchmark_cli"]["real_runner_invoked"] is False, payload
    assert payload["benchmark_cli"]["real_codex_invoked"] is False, payload

    event = payload["benchmark_run"]
    assert event["schema_version"] == "benchmark_run_v0", event
    assert event["source_runner"] == "loopx_terminal_bench_cli_skeleton", event
    assert event["benchmark_id"] == BENCHMARK_ID, event
    assert event["mode"] == RUN_MODE, event
    assert event["agent"]["model"] == "gpt-5.5", event
    assert event["progress"]["n_total_trials"] == 0, event
    assert event["metrics"]["cost_usd"] == 0, event
    assert event["trials"][0]["exception_type"] == "fake_managed_worker_only_no_real_case", event
    assert event["validation"]["all_passed"] is True, event
    assert event["validation"]["failed_checks"] == [], event
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert event["official_task_score"]["kind"] == "not_run", event
    assert event["official_task_score"].get("value") is None, event
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
    assert summary["benchmark_id"] == BENCHMARK_ID, summary
    assert summary["progress"]["n_total_trials"] == 0, summary
    assert summary["validation"]["all_passed"] is True, summary
    assert status["event_ledger_summary"]["totals"]["benchmark_runs_24h"] == 1, status
    assert_public_safe(summary)


def assert_fake_worker_rejected_for_controls(registry_path: Path, runtime: Path) -> None:
    args = common_args(registry_path, runtime)
    mode_index = args.index("--mode") + 1
    args[mode_index] = "hardened-codex"
    result = run_cli(args, check=False)
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False, payload
    assert "only supported" in payload["error"], payload


def main() -> None:
    assert_doc_contract()
    with tempfile.TemporaryDirectory(prefix="terminal-bench-cli-dry-run-") as tmp:
        registry_path, runtime = write_fixture(Path(tmp))
        dry_payload = run_cli_json(common_args(registry_path, runtime))
        assert_payload(dry_payload, appended=False)

        execute_payload = run_cli_json(
            common_args(registry_path, runtime)
            + [
                "--delivery-batch-scale",
                "multi_surface",
                "--delivery-outcome",
                "outcome_progress",
                "--execute",
            ]
        )
        assert_payload(execute_payload, appended=True)
        assert_status_projection(registry_path, runtime)
        assert_fake_worker_rejected_for_controls(registry_path, runtime)

    print(
        "terminal-bench-cli-dry-run-fake-worker-smoke ok "
        f"mode={RUN_MODE} appended=True real_run=False"
    )


if __name__ == "__main__":
    main()
