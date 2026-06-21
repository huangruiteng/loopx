#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench CLI bridge runner fixture path."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "terminal-bench-loopx-cli-bridge-runner-fixture"


def write_json(path: Path, payload: dict[str, object]) -> None:
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
        "# Terminal-Bench LoopX CLI Bridge Runner Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Run the bridge runner fixture.\n",
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


def run_json(argv: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict), payload
    return payload


def assert_payload(payload: dict[str, object], *, appended: bool) -> None:
    assert payload.get("ok") is True, payload
    assert payload.get("appended") is appended, payload
    assert payload.get("classification") == (
        "terminal_bench_codex_loopx_cli_bridge_contract_runner_fixture_v0"
    ), payload
    benchmark_run = payload.get("benchmark_run")
    assert isinstance(benchmark_run, dict), payload
    assert benchmark_run["mode"] == "codex_loopx_cli_bridge_contract_fixture", benchmark_run
    assert benchmark_run["source_runner"] == (
        "loopx_terminal_bench_codex_loopx_cli_bridge_contract_runner_fixture"
    ), benchmark_run
    assert benchmark_run["real_run"] is False, benchmark_run
    assert benchmark_run["submit_eligible"] is False, benchmark_run
    assert benchmark_run["loopx_cli_bridge_contract_available"] is True, benchmark_run
    assert benchmark_run["loopx_cli_bridge_trace_observed"] is True, benchmark_run
    assert benchmark_run["loopx_cli_bridge_scope"] == (
        "host_agent_runner_fixture_no_terminal_bench_worker"
    ), benchmark_run

    counters = benchmark_run.get("interaction_counters")
    assert isinstance(counters, dict), benchmark_run
    assert counters["loopx_state_reads"] == 5, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "bridge_append_benchmark_run_dry_run", counters
    assert counters["counter_trust_level"] == "runner_bridge_contract_fixture_observed", counters
    cli_calls = counters.get("loopx_cli_calls")
    assert isinstance(cli_calls, dict), counters
    assert cli_calls["total"] == 6, cli_calls
    for command in (
        "status",
        "quota_should_run",
        "todo_list",
        "history",
        "check",
        "append_benchmark_run",
    ):
        assert cli_calls[command] == 1, cli_calls
    runtime_calls = counters.get("codex_runtime_goal_tool_calls")
    assert isinstance(runtime_calls, dict), counters
    assert runtime_calls["total"] == 0, runtime_calls

    cli = payload.get("benchmark_cli")
    assert isinstance(cli, dict), payload
    assert cli["cli_bridge_contract"] is True, cli
    assert cli["cli_bridge_trace_observed"] is True, cli
    assert cli["real_runner_invoked"] is False, cli
    assert cli["real_codex_invoked"] is False, cli


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="terminal-bench-cli-bridge-runner-") as raw_root:
        registry_path, runtime = write_fixture(Path(raw_root))
        base = [
            sys.executable,
            "-m",
            "loopx.cli",
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
            "--cli-bridge-contract",
            "--no-global-sync",
        ]
        dry_run = run_json(base)
        assert_payload(dry_run, appended=False)

        executed = run_json([*base, "--execute"])
        assert_payload(executed, appended=True)

    print("terminal-bench-loopx-cli-bridge-runner-smoke ok cli_calls=6")


if __name__ == "__main__":
    main()
