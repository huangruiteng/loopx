#!/usr/bin/env python3
"""Smoke-test the true codex-loopx fake-worker CLI mode."""

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
DOC = TOPIC_DIR / "terminal-bench-codex-loopx-fake-worker-v0.md"
README = TOPIC_DIR / "README.md"

GOAL_ID = "terminal-bench-codex-loopx-fixture"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_ID = "build-cython-ext"
MODE = "codex-loopx"
RUN_MODE = "codex_loopx_fake_worker_wrapper"
WORKER_MODE = "codex_loopx_cli"

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench Codex LoopX Fake Worker V0",
    "loopx benchmark run terminal-bench --mode codex-loopx --fake-worker",
    "codex_loopx_fake_worker_wrapper",
    "codex_goal_mode",
    "loopx-managed-codex",
    "loopx_cli_calls.total=6",
    "loopx_state_reads=4",
    "loopx_state_writes=1",
    "worker_loopx_writeback",
    "fake_worker_fixture_observed",
    "python3 examples/terminal-bench-codex-loopx-fake-worker-smoke.py",
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
        "# Terminal-Bench Codex LoopX Fake Worker Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Run the codex-loopx fake-worker skeleton.\n",
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


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
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
        MODE,
        "--dataset",
        BENCHMARK_ID,
        "--include-task-name",
        TASK_ID,
        "--fake-worker",
        "--no-global-sync",
    ]


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 22000, len(text)


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
    assert "terminal-bench-codex-loopx-fake-worker-v0.md" in readme, readme
    assert_public_safe(text)


def assert_counters(counters: dict[str, Any]) -> None:
    assert counters["schema_version"] == "terminal_bench_loopx_interaction_counters_v0", counters
    assert counters["prompt_policy_injected"] is True, counters
    assert counters["harness_skill_or_packet_injected"] is True, counters
    assert counters["codex_runtime_goal_tool_calls"]["total"] == 0, counters
    assert counters["loopx_cli_calls"]["status"] == 1, counters
    assert counters["loopx_cli_calls"]["quota_should_run"] == 1, counters
    assert counters["loopx_cli_calls"]["todo_list"] == 1, counters
    assert counters["loopx_cli_calls"]["history"] == 1, counters
    assert counters["loopx_cli_calls"]["check"] == 1, counters
    assert counters["loopx_cli_calls"]["append_benchmark_run"] == 1, counters
    assert counters["loopx_cli_calls"]["total"] == 6, counters
    assert counters["loopx_state_reads"] == 4, counters
    assert counters["loopx_state_writes"] == 1, counters
    assert counters["case_result_writeback"] == "worker_loopx_writeback", counters
    assert counters["counter_trust_level"] == "fake_worker_fixture_observed", counters
    assert counters["raw_trace_recorded"] is False, counters
    assert counters["raw_task_prompt_recorded"] is False, counters


def assert_payload(payload: dict[str, Any], *, appended: bool) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    assert payload["dry_run"] is (not appended), payload
    assert payload["classification"] == "terminal_bench_codex_loopx_fake_worker_v0", payload
    assert payload["benchmark_cli"]["benchmark"] == "terminal-bench", payload
    assert payload["benchmark_cli"]["mode"] == MODE, payload
    assert payload["benchmark_cli"]["fake_worker"] is True, payload
    assert payload["benchmark_cli"]["real_runner_invoked"] is False, payload
    assert payload["benchmark_cli"]["real_codex_invoked"] is False, payload

    event = payload["benchmark_run"]
    assert event["schema_version"] == "benchmark_run_v0", event
    assert event["mode"] == RUN_MODE, event
    assert event["worker_mode"] == WORKER_MODE, event
    assert event["agent"]["import_path"] == "loopx.terminal_bench_agent:GoalHarnessManagedCodex", event
    assert event["progress"]["n_total_trials"] == 0, event
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert event["official_task_score"]["kind"] == "not_run", event
    assert event["loopx_inside_case"] is True, event
    assert event["official_score_comparable_to_native_codex"] is False, event
    assert event["model_plus_harness_pair"] is True, event
    assert event["leaderboard_evidence"] is False, event
    assert event["trials"][0]["exception_type"] == "fake_codex_loopx_worker_only_no_real_case", event
    assert_counters(event["interaction_counters"])
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
    assert summary["worker_mode"] == WORKER_MODE, summary
    assert summary["loopx_inside_case"] is True, summary
    assert_counters(summary["interaction_counters"])
    assert_public_safe(summary)


def main() -> None:
    assert_doc_contract()
    with tempfile.TemporaryDirectory(
        prefix="loopx-codex-loopx-fake-worker-smoke-"
    ) as raw_root:
        registry_path, runtime = write_fixture(Path(raw_root))
        dry_run_payload = run_cli_json(common_args(registry_path, runtime))
        assert_payload(dry_run_payload, appended=False)

        append_payload = run_cli_json([*common_args(registry_path, runtime), "--execute"])
        assert_payload(append_payload, appended=True)
        assert_status_projection(registry_path, runtime)

    print("terminal-bench-codex-loopx-fake-worker-smoke ok cli_calls=6")


if __name__ == "__main__":
    main()
